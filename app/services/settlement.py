import json
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.trip import Trip, Traveler
from app.models.expense import Expense

class SettlementService:
    """
    Splitwise-style multi-person expense splitting and minimum cash flow 
    debt simplification engine.
    """

    @classmethod
    def calculate_settlements(cls, db: Session, trip_id: int) -> Dict[str, Any]:
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return {"error": f"Trip #{trip_id} not found"}

        # 1. Discover all travelers in this trip
        registered_travelers = [t.name for t in trip.travelers]
        primary_name = registered_travelers[0] if registered_travelers else "You"

        expenses = db.query(Expense).filter(Expense.trip_id == trip_id).all()

        # Track total paid and total owed by each person
        # balances[person] = total_paid - total_share
        all_participants = set(registered_travelers)
        if not all_participants:
            all_participants.add(primary_name)

        paid_amounts: Dict[str, float] = {p: 0.0 for p in all_participants}
        share_amounts: Dict[str, float] = {p: 0.0 for p in all_participants}
        expense_breakdowns = []

        for exp in expenses:
            cost = float(exp.amount_home)
            payer = (exp.paid_by_name or primary_name).strip()
            all_participants.add(payer)
            if payer not in paid_amounts:
                paid_amounts[payer] = 0.0
                share_amounts[payer] = 0.0

            paid_amounts[payer] += cost

            # Determine who split this expense
            split_members = []
            if exp.split_with:
                try:
                    loaded = json.loads(exp.split_with)
                    if isinstance(loaded, list) and loaded:
                        split_members = [str(m).strip() for m in loaded]
                except Exception:
                    split_members = []

            # If not in split_with, check split_notes e.g. "split with Sam, Rahul"
            if not split_members and exp.split_notes:
                notes = exp.split_notes
                # Detect names
                if "split with" in notes.lower():
                    after = notes.lower().split("split with", 1)[1]
                    raw_names = [n.strip().title() for n in after.replace("and", ",").split(",") if n.strip()]
                    if raw_names:
                        split_members = [payer] + raw_names

            # Default: split equally among all currently registered travelers
            if not split_members:
                split_members = list(all_participants) if all_participants else [payer]

            # Register any new names
            for m in split_members:
                all_participants.add(m)
                if m not in paid_amounts:
                    paid_amounts[m] = 0.0
                    share_amounts[m] = 0.0

            # Compute individual share for this expense
            num_split = len(split_members)
            per_person = round(cost / num_split, 2)
            remainder = round(cost - (per_person * num_split), 2)

            for idx, member in enumerate(split_members):
                # add penny remainder to first member to keep exact zero-sum
                member_share = per_person + (remainder if idx == 0 else 0.0)
                share_amounts[member] += member_share

            expense_breakdowns.append({
                "id": exp.id,
                "description": exp.description,
                "total_amount": cost,
                "payer": payer,
                "split_with": split_members,
                "per_person": per_person
            })

        # 2. Compute Net Balances
        net_balances: Dict[str, float] = {}
        for p in all_participants:
            net_balances[p] = round(paid_amounts.get(p, 0.0) - share_amounts.get(p, 0.0), 2)

        # 3. Minimum Cash Flow Debt Simplification Algorithm
        simplified_debts = cls._simplify_debts(net_balances)

        # 4. Generate WhatsApp / Shareable formatted message
        whatsapp_message = cls._generate_share_message(
            trip_name=trip.name,
            currency=trip.home_currency,
            net_balances=net_balances,
            simplified_debts=simplified_debts
        )

        return {
            "trip_id": trip.id,
            "trip_name": trip.name,
            "home_currency": trip.home_currency,
            "participants": list(all_participants),
            "paid_totals": paid_amounts,
            "share_totals": share_amounts,
            "net_balances": net_balances,
            "simplified_debts": simplified_debts,
            "whatsapp_message": whatsapp_message,
            "total_group_spend": round(sum(paid_amounts.values()), 2)
        }

    @classmethod
    def _simplify_debts(cls, balances: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Greedy minimum cash flow debt settlement algorithm.
        Reduces multi-party debts to the minimal set of direct bilateral payments.
        """
        # Separate debtors and creditors
        debtors = []   # (person, amount_they_owe)
        creditors = [] # (person, amount_they_are_owed)

        for person, bal in balances.items():
            if bal < -0.01:
                debtors.append([person, -bal])
            elif bal > 0.01:
                creditors.append([person, bal])

        # Sort descending by amount
        debtors.sort(key=lambda x: x[1], reverse=True)
        creditors.sort(key=lambda x: x[1], reverse=True)

        payments = []
        d_idx = 0
        c_idx = 0

        while d_idx < len(debtors) and c_idx < len(creditors):
            debtor_name, debt_amt = debtors[d_idx]
            creditor_name, credit_amt = creditors[c_idx]

            transfer_amt = min(debt_amt, credit_amt)
            if transfer_amt > 0.01:
                payments.append({
                    "from_person": debtor_name,
                    "to_person": creditor_name,
                    "amount": round(transfer_amt, 2)
                })

            debtors[d_idx][1] -= transfer_amt
            creditors[c_idx][1] -= transfer_amt

            if debtors[d_idx][1] <= 0.01:
                d_idx += 1
            if creditors[c_idx][1] <= 0.01:
                c_idx += 1

        return payments

    @classmethod
    def _generate_share_message(
        cls,
        trip_name: str,
        currency: str,
        net_balances: Dict[str, float],
        simplified_debts: List[Dict[str, Any]]
    ) -> str:
        lines = [
            f"✈️ *{trip_name} - Group Expense Settlements*",
            f"----------------------------------------",
            "📊 *Net Balances:*"
        ]

        for p, b in sorted(net_balances.items(), key=lambda x: x[1], reverse=True):
            if b > 0.01:
                lines.append(f"  • {p}: +{currency} {b:,.2f} *(Gets back)*")
            elif b < -0.01:
                lines.append(f"  • {p}: -{currency} {abs(b):,.2f} *(Owes)*")
            else:
                lines.append(f"  • {p}: {currency} 0.00 *(Settled)*")

        lines.append("")
        lines.append("🤝 *Simplified Payments (Minimal Transfers):*")
        if simplified_debts:
            for idx, pay in enumerate(simplified_debts, 1):
                lines.append(f"  {idx}️⃣ *{pay['from_person']}* ➡️ pays *{pay['to_person']}* {currency} {pay['amount']:,.2f}")
        else:
            lines.append("  🎉 All expenses are settled!")

        lines.append("")
        lines.append("💳 *Settle up via UPI, GPay, or Cash.*")
        return "\n".join(lines)
