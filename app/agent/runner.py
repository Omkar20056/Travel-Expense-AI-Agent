import json
import re
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from google import genai
from google.genai import types

from app.config import settings
from app.models.trip import Trip
from app.models.expense import Expense
from app.models.category import Category
from app.schemas.chat import ChatMessage, ChatResponse, ToolExecutionResult
from app.services.currency import CurrencyService
from app.services.categorization import CategorizationService
from app.services.budget import BudgetService
from app.services.receipt_parser import ReceiptParserService
from app.services.sms_parser import SmsParserService
from app.services.settlement import SettlementService
from app.services.anomaly_detector import AnomalyDetectorService
from app.agent.tools import AGENT_TOOLS
from app.agent.prompts import build_system_prompt

class AgentRunner:
    @classmethod
    def execute_tool(
        cls,
        tool_name: str,
        args: Dict[str, Any],
        db: Session,
        active_trip: Optional[Trip] = None
    ) -> Dict[str, Any]:
        """Dispatches and executes a tool call against the database and services."""
        if tool_name == "add_expense":
            return cls._tool_add_expense(args, db, active_trip)
        elif tool_name == "edit_expense":
            return cls._tool_edit_expense(args, db)
        elif tool_name == "delete_expense":
            return cls._tool_delete_expense(args, db)
        elif tool_name == "list_expenses":
            return cls._tool_list_expenses(args, db, active_trip)
        elif tool_name == "get_summary":
            return cls._tool_get_summary(args, db, active_trip)
        elif tool_name == "convert_currency":
            return cls._tool_convert_currency(args, db)
        elif tool_name == "set_budget":
            return cls._tool_set_budget(args, db, active_trip)
        elif tool_name == "parse_receipt":
            return cls._tool_parse_receipt(args, db, active_trip)
        elif tool_name == "parse_payment_sms":
            return cls._tool_parse_payment_sms(args, db, active_trip)
        elif tool_name == "get_group_settlements":
            return cls._tool_get_group_settlements(args, db, active_trip)
        elif tool_name == "check_spending_anomalies":
            return cls._tool_check_spending_anomalies(args, db, active_trip)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    @classmethod
    def _tool_add_expense(cls, args: Dict[str, Any], db: Session, active_trip: Optional[Trip]) -> Dict[str, Any]:
        trip_id = args.get("trip_id") or (active_trip.id if active_trip else None)
        if not trip_id:
            return {"error": "No active trip found to attach expense to."}

        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return {"error": f"Trip with ID {trip_id} not found."}

        amount = float(args["amount"])
        currency = args["currency"].upper().strip()
        description = args["description"].strip()
        date_val = datetime.strptime(args["date"], "%Y-%m-%d").date()
        merchant = args.get("merchant")
        city = args.get("city")
        split_notes = args.get("split_notes")
        paid_by_name = args.get("paid_by_name")
        split_with = args.get("split_with")
        payment_mode = args.get("payment_mode", "Cash")
        reference_id = args.get("reference_id")
        cat_name = args.get("category")

        # Resolve category
        if cat_name:
            category = CategorizationService.get_category_by_name(db, cat_name)
            if not category:
                category = CategorizationService.classify(db, description, merchant)
        else:
            category = CategorizationService.classify(db, description, merchant)

        # Currency conversion
        amount_home, rate = CurrencyService.convert(
            amount=amount,
            from_currency=currency,
            to_currency=trip.home_currency,
            rate_date=date_val,
            db=db
        )

        expense = Expense(
            trip_id=trip.id,
            category_id=category.id,
            date=date_val,
            amount=amount,
            currency=currency,
            exchange_rate=rate,
            amount_home=amount_home,
            merchant=merchant,
            description=description,
            city=city,
            split_notes=split_notes,
            paid_by_name=paid_by_name,
            split_with=split_with,
            payment_mode=payment_mode,
            reference_id=reference_id,
            raw_input=f"{amount} {currency} for {description}"
        )
        db.add(expense)
        db.flush()

        # Anomaly and Duplicate swipe detection
        is_anomaly, anomaly_reason = AnomalyDetectorService.check_anomaly(expense, db)
        if is_anomaly:
            expense.is_anomaly = True
            expense.anomaly_reason = anomaly_reason

        db.commit()
        db.refresh(expense)

        return {
            "success": True,
            "expense_id": expense.id,
            "amount": amount,
            "currency": currency,
            "amount_home": amount_home,
            "home_currency": trip.home_currency,
            "category": category.name,
            "description": description,
            "merchant": merchant,
            "city": city,
            "date": date_val.strftime("%Y-%m-%d"),
            "split_notes": split_notes,
            "paid_by_name": paid_by_name,
            "payment_mode": payment_mode,
            "reference_id": reference_id,
            "is_anomaly": is_anomaly,
            "anomaly_reason": anomaly_reason
        }

    @classmethod
    def _tool_edit_expense(cls, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
        expense_id = int(args["expense_id"])
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not expense:
            return {"error": f"Expense with ID {expense_id} not found."}

        trip = expense.trip
        recalculate_currency = False

        if "amount" in args and args["amount"] is not None:
            expense.amount = float(args["amount"])
            recalculate_currency = True

        if "currency" in args and args["currency"]:
            expense.currency = args["currency"].upper().strip()
            recalculate_currency = True

        if "date" in args and args["date"]:
            expense.date = datetime.strptime(args["date"], "%Y-%m-%d").date()
            recalculate_currency = True

        if "merchant" in args and args["merchant"] is not None:
            expense.merchant = args["merchant"]

        if "description" in args and args["description"]:
            expense.description = args["description"]

        if "city" in args and args["city"] is not None:
            expense.city = args["city"]

        if "split_notes" in args and args["split_notes"] is not None:
            expense.split_notes = args["split_notes"]

        if "category" in args and args["category"]:
            cat = CategorizationService.get_category_by_name(db, args["category"])
            if cat:
                expense.category_id = cat.id
                if args.get("learn_category_rule"):
                    pattern = expense.merchant or expense.description
                    CategorizationService.learn_rule(db, pattern, cat.name)

        if recalculate_currency:
            converted, rate = CurrencyService.convert(
                float(expense.amount),
                expense.currency,
                trip.home_currency,
                expense.date,
                db
            )
            expense.amount_home = converted
            expense.exchange_rate = rate

        db.commit()
        db.refresh(expense)

        return {
            "success": True,
            "expense_id": expense.id,
            "amount": float(expense.amount),
            "currency": expense.currency,
            "amount_home": float(expense.amount_home),
            "home_currency": trip.home_currency,
            "category": expense.category.name,
            "description": expense.description,
            "merchant": expense.merchant,
            "city": expense.city,
            "date": expense.date.strftime("%Y-%m-%d")
        }

    @classmethod
    def _tool_delete_expense(cls, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
        expense_id = int(args["expense_id"])
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not expense:
            return {"error": f"Expense with ID {expense_id} not found."}

        desc = expense.description
        amount = float(expense.amount)
        curr = expense.currency
        db.delete(expense)
        db.commit()
        return {
            "success": True,
            "deleted_id": expense_id,
            "description": desc,
            "amount": amount,
            "currency": curr
        }

    @classmethod
    def _tool_list_expenses(cls, args: Dict[str, Any], db: Session, active_trip: Optional[Trip]) -> Dict[str, Any]:
        trip_id = args.get("trip_id") or (active_trip.id if active_trip else None)
        query = db.query(Expense)
        if trip_id:
            query = query.filter(Expense.trip_id == trip_id)

        if args.get("category"):
            cat = CategorizationService.get_category_by_name(db, args["category"])
            if cat:
                query = query.filter(Expense.category_id == cat.id)

        if args.get("city"):
            query = query.filter(Expense.city.ilike(f"%{args['city'].strip()}%"))

        if args.get("start_date"):
            query = query.filter(Expense.date >= datetime.strptime(args["start_date"], "%Y-%m-%d").date())

        if args.get("end_date"):
            query = query.filter(Expense.date <= datetime.strptime(args["end_date"], "%Y-%m-%d").date())

        limit = args.get("limit", 20)
        items = query.order_by(Expense.date.desc(), Expense.id.desc()).limit(limit).all()

        return {
            "count": len(items),
            "expenses": [
                {
                    "id": exp.id,
                    "date": exp.date.strftime("%Y-%m-%d"),
                    "amount": float(exp.amount),
                    "currency": exp.currency,
                    "amount_home": float(exp.amount_home),
                    "description": exp.description,
                    "category": exp.category.name,
                    "merchant": exp.merchant,
                    "city": exp.city
                }
                for exp in items
            ]
        }

    @classmethod
    def _tool_get_summary(cls, args: Dict[str, Any], db: Session, active_trip: Optional[Trip]) -> Dict[str, Any]:
        trip_id = args.get("trip_id") or (active_trip.id if active_trip else None)
        if not trip_id:
            return {"error": "No active trip found."}

        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return {"error": f"Trip with ID {trip_id} not found."}

        category_filter = args.get("category")
        city_filter = args.get("city")

        if category_filter or city_filter:
            q = db.query(Expense).filter(Expense.trip_id == trip.id)
            if category_filter:
                cat = CategorizationService.get_category_by_name(db, category_filter)
                if cat:
                    q = q.filter(Expense.category_id == cat.id)
            if city_filter:
                q = q.filter(Expense.city.ilike(f"%{city_filter.strip()}%"))

            filtered_expenses = q.all()
            total_filtered = sum(float(e.amount_home) for e in filtered_expenses)
            return {
                "trip_id": trip.id,
                "category_filter": category_filter,
                "city_filter": city_filter,
                "total_spent_home": round(total_filtered, 2),
                "home_currency": trip.home_currency,
                "count": len(filtered_expenses)
            }

        summary = BudgetService.get_trip_summary(trip, db)
        return summary.model_dump()

    @classmethod
    def _tool_convert_currency(cls, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
        amount = float(args["amount"])
        from_curr = args["from_currency"].upper().strip()
        to_curr = args["to_currency"].upper().strip()
        rate_date = datetime.strptime(args["date"], "%Y-%m-%d").date() if args.get("date") else date.today()

        converted, rate = CurrencyService.convert(amount, from_curr, to_curr, rate_date, db)
        return {
            "original_amount": amount,
            "from_currency": from_curr,
            "converted_amount": converted,
            "to_currency": to_curr,
            "exchange_rate": rate,
            "date": rate_date.strftime("%Y-%m-%d")
        }

    @classmethod
    def _tool_set_budget(cls, args: Dict[str, Any], db: Session, active_trip: Optional[Trip]) -> Dict[str, Any]:
        trip_id = args.get("trip_id") or (active_trip.id if active_trip else None)
        if not trip_id:
            return {"error": "No active trip found."}
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return {"error": f"Trip with ID {trip_id} not found."}

        if "total_budget" in args and args["total_budget"] is not None:
            trip.total_budget = float(args["total_budget"])
        if "home_currency" in args and args["home_currency"]:
            trip.home_currency = args["home_currency"].upper().strip()

        db.commit()
        db.refresh(trip)
        return {
            "success": True,
            "trip_id": trip.id,
            "total_budget": float(trip.total_budget),
            "home_currency": trip.home_currency
        }

    @classmethod
    def _tool_parse_receipt(cls, args: Dict[str, Any], db: Session, active_trip: Optional[Trip]) -> Dict[str, Any]:
        receipt_id = args["receipt_id"]
        parsed = ReceiptParserService.parse_receipt(receipt_id)

        if args.get("auto_save") and parsed.get("amount") and parsed.get("currency"):
            add_args = {
                "amount": parsed["amount"],
                "currency": parsed["currency"],
                "description": f"Receipt from {parsed.get('merchant') or 'Merchant'}",
                "date": parsed.get("date") or date.today().strftime("%Y-%m-%d"),
                "category": parsed.get("suggested_category"),
                "merchant": parsed.get("merchant"),
                "trip_id": args.get("trip_id") or (active_trip.id if active_trip else None)
            }
            save_result = cls._tool_add_expense(add_args, db, active_trip)
            return {"parsed": parsed, "saved_expense": save_result}

        return {"parsed": parsed}

    @classmethod
    def _tool_parse_payment_sms(cls, args: Dict[str, Any], db: Session, active_trip: Optional[Trip]) -> Dict[str, Any]:
        sms_text = args.get("sms_text", "").strip()
        trip_id = args.get("trip_id") or (active_trip.id if active_trip else None)
        if not trip_id:
            return {"error": "No active trip found to attach expense to."}

        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return {"error": f"Trip #{trip_id} not found."}

        parsed = SmsParserService.parse_sms(sms_text, default_currency=trip.home_currency, db=db)
        if not parsed.get("success") or not parsed.get("amount"):
            return {"error": "Could not extract valid transaction details from the provided SMS."}

        add_args = {
            "amount": parsed["amount"],
            "currency": parsed["currency"],
            "description": parsed["description"],
            "date": parsed["date"],
            "category": parsed.get("category", "other"),
            "merchant": parsed.get("merchant"),
            "payment_mode": parsed.get("payment_mode", "UPI"),
            "reference_id": parsed.get("reference_id"),
            "trip_id": trip.id
        }
        res = cls._tool_add_expense(add_args, db, trip)
        res["parsed_sms"] = parsed
        return res

    @classmethod
    def _tool_get_group_settlements(cls, args: Dict[str, Any], db: Session, active_trip: Optional[Trip]) -> Dict[str, Any]:
        trip_id = args.get("trip_id") or (active_trip.id if active_trip else None)
        if not trip_id:
            return {"error": "No active trip found."}
        return SettlementService.calculate_settlements(db, trip_id)

    @classmethod
    def _tool_check_spending_anomalies(cls, args: Dict[str, Any], db: Session, active_trip: Optional[Trip]) -> Dict[str, Any]:
        trip_id = args.get("trip_id") or (active_trip.id if active_trip else None)
        if not trip_id:
            return {"error": "No active trip found."}

        expenses = db.query(Expense).filter(Expense.trip_id == trip_id).all()
        anomalies = []
        for exp in expenses:
            if exp.is_anomaly:
                anomalies.append({
                    "id": exp.id,
                    "description": exp.description,
                    "amount": float(exp.amount),
                    "currency": exp.currency,
                    "date": exp.date.strftime("%Y-%m-%d"),
                    "reason": exp.anomaly_reason
                })
        return {
            "trip_id": trip_id,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies
        }

    @classmethod
    def run_turn(
        cls,
        user_message: str,
        history: List[ChatMessage],
        db: Session,
        active_trip: Optional[Trip] = None
    ) -> ChatResponse:
        """
        Coordinates the LLM turn with tool calling using Google Gemini API.
        Falls back to local rule-based engine if GEMINI_API_KEY is not set.
        """
        api_key = settings.GEMINI_API_KEY

        # If no Gemini API key set, use local rule-based fallback
        if not api_key or api_key == "your_google_ai_studio_api_key_here":
            return cls._rule_based_turn(user_message, db, active_trip)

        try:
            client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=10000))
            system_prompt = build_system_prompt(active_trip)

            # Build Gemini Tool declarations
            gemini_tools = [
                types.Tool(function_declarations=[
                    types.FunctionDeclaration(
                        name=t["name"],
                        description=t["description"],
                        parameters=t["input_schema"]
                    )
                    for t in AGENT_TOOLS
                ])
            ]

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=gemini_tools,
                temperature=0.1
            )

            # Build multi-turn contents
            contents: List[types.Content] = []
            for m in history:
                role = "user" if m.role == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m.content)]))
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

            tools_executed: List[ToolExecutionResult] = []

            # First turn: call Gemini
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=config
            )

            # Handle function calling loop
            while response.function_calls:
                # Add model response to conversation history
                if response.candidates and response.candidates[0].content:
                    contents.append(response.candidates[0].content)

                fn_response_parts = []
                for fn_call in response.function_calls:
                    fn_name = fn_call.name
                    fn_args = dict(fn_call.args) if fn_call.args else {}

                    # Execute tool
                    exec_result = cls.execute_tool(fn_name, fn_args, db, active_trip)
                    tools_executed.append(ToolExecutionResult(
                        tool=fn_name,
                        arguments=fn_args,
                        result=exec_result
                    ))

                    fn_response_parts.append(
                        types.Part.from_function_response(
                            name=fn_name,
                            response={"result": exec_result}
                        )
                    )

                # Feed function response back to Gemini
                contents.append(types.Content(role="user", parts=fn_response_parts))

                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=contents,
                    config=config
                )

            final_text = (response.text or "").strip()
            is_clarification = "?" in final_text and not tools_executed

            return ChatResponse(
                response=final_text,
                clarification_needed=is_clarification,
                tools_called=tools_executed,
                active_trip_id=active_trip.id if active_trip else None
            )

        except Exception as e:
            # Fallback to local rule-based parser if API call fails
            import logging
            logging.getLogger("travel_agent").warning("Gemini API call failed (%s), falling back to local agent parser.", e)
            fallback_resp = cls._rule_based_turn(user_message, db, active_trip)
            return fallback_resp

    @classmethod
    def _rule_based_turn(
        cls,
        user_message: str,
        db: Session,
        active_trip: Optional[Trip] = None
    ) -> ChatResponse:
        """Deterministic parser for local testing and offline execution."""
        msg = user_message.strip()
        msg_lower = msg.lower()

        # 1. Budget / Summary queries
        if any(w in msg_lower for w in ["summary", "budget", "track", "how much did i spend", "spend on", "how are we doing"]):
            group_by = "overall"
            cat_filter = None
            city_filter = None

            for cat in ["food", "transport", "lodging", "activities", "shopping", "fees"]:
                if cat in msg_lower:
                    cat_filter = cat
                    break

            if active_trip:
                try:
                    dests = json.loads(active_trip.destinations)
                    for d in dests:
                        if d.lower() in msg_lower:
                            city_filter = d
                            break
                except Exception:
                    pass

            result = cls.execute_tool("get_summary", {
                "group_by": group_by,
                "category": cat_filter,
                "city": city_filter
            }, db, active_trip)

            if cat_filter or city_filter:
                filter_desc = f"{cat_filter or ''} in {city_filter or ''}".strip()
                resp_text = f"You have spent {result.get('home_currency', 'USD')} {result.get('total_spent_home', 0.0):.2f} on {filter_desc} ({result.get('count', 0)} expenses)."
            else:
                b = result.get("budget_status", {})
                warn = b.get("warning_message") or ""
                warn_suffix = f" {warn}" if warn else ""
                resp_text = (
                    f"Spent {b.get('home_currency', 'USD')} {b.get('total_spent_home', 0.0):,.2f} of "
                    f"{b.get('home_currency', 'USD')} {b.get('total_budget', 0.0):,.2f} budget "
                    f"({b.get('percentage_used', 0.0)}% used).{warn_suffix}"
                )

            return ChatResponse(
                response=resp_text,
                clarification_needed=False,
                tools_called=[ToolExecutionResult(tool="get_summary", arguments={"category": cat_filter, "city": city_filter}, result=result)],
                active_trip_id=active_trip.id if active_trip else None
            )

        # 2. Category correction learning
        correct_match = re.search(r"(?:change|should be|is) (?:expense )?#?(\d+) (?:to )?(\w+)", msg_lower)
        if correct_match:
            exp_id = int(correct_match.group(1))
            new_cat = correct_match.group(2)
            res = cls.execute_tool("edit_expense", {
                "expense_id": exp_id,
                "category": new_cat,
                "learn_category_rule": True
            }, db, active_trip)
            if "error" in res:
                return ChatResponse(response=res["error"], clarification_needed=False)
            return ChatResponse(
                response=f"Updated: Expense #{exp_id} category changed to {new_cat.capitalize()}, and I've saved this preference for future expenses.",
                tools_called=[ToolExecutionResult(tool="edit_expense", arguments={"expense_id": exp_id, "category": new_cat}, result=res)],
                active_trip_id=active_trip.id if active_trip else None
            )

        # 3. Transaction / UPI SMS auto-parsing
        if any(marker in msg_lower for marker in ["debited", "sent rs", "sent inr", "paid rs", "paid inr", "upi ref", "vpa", "spent on your credit card", "txn id", "txn:"]):
            res = cls.execute_tool("parse_payment_sms", {"sms_text": msg}, db, active_trip)
            if "error" in res:
                return ChatResponse(response=f"SMS Parsing failed: {res['error']}", clarification_needed=False)
            amt = res["amount"]
            curr = res["currency"]
            merchant = res.get("merchant", "Vendor")
            cat = res.get("category", "other").capitalize()
            mode = res.get("payment_mode", "UPI")
            ref = f" (Ref: {res.get('reference_id')})" if res.get("reference_id") else ""
            warn = f" ⚠️ {res['anomaly_reason']}" if res.get("is_anomaly") else ""
            one_line = f"Parsed from {mode} SMS: Logged #{res['expense_id']} for {curr} {amt:,.2f} at {merchant} ({cat}){ref}.{warn}"
            return ChatResponse(
                response=one_line,
                tools_called=[ToolExecutionResult(tool="parse_payment_sms", arguments={"sms_text": msg}, result=res)],
                active_trip_id=active_trip.id if active_trip else None
            )

        # 4. Group Debt Settlement / Splitwise
        if any(w in msg_lower for w in ["who owes whom", "settle", "settlement", "splitwise", "balances", "how do we split", "whatsapp summary"]):
            res = cls.execute_tool("get_group_settlements", {}, db, active_trip)
            if "error" in res:
                return ChatResponse(response=res["error"], clarification_needed=False)
            return ChatResponse(
                response=res.get("whatsapp_message", "All expenses are settled!"),
                tools_called=[ToolExecutionResult(tool="get_group_settlements", arguments={}, result=res)],
                active_trip_id=active_trip.id if active_trip else None
            )

        # 5. Anomaly / Duplicate check
        if any(w in msg_lower for w in ["anomaly", "anomalies", "duplicate", "duplicates", "overcharge", "suspicious"]):
            res = cls.execute_tool("check_spending_anomalies", {}, db, active_trip)
            if "error" in res:
                return ChatResponse(response=res["error"], clarification_needed=False)
            count = res.get("anomaly_count", 0)
            if count == 0:
                resp_text = "✅ Great news! No duplicate expenses, price surges, or anomalies detected on this trip."
            else:
                anoms = res.get("anomalies", [])
                lines = [f"⚠️ Found {count} potential anomalies on this trip:"]
                for a in anoms:
                    lines.append(f"• Expense #{a['id']} ({a['currency']} {a['amount']:,.2f} on {a['date']}): {a['reason']}")
                resp_text = "\n".join(lines)
            return ChatResponse(
                response=resp_text,
                tools_called=[ToolExecutionResult(tool="check_spending_anomalies", arguments={}, result=res)],
                active_trip_id=active_trip.id if active_trip else None
            )

        # 6. Expense logging pattern: supports $, €, £, ¥, ₹ and word currencies including rs, rupees, inr
        currency_map = {
            "$": "USD", "dollar": "USD", "dollars": "USD", "usd": "USD",
            "€": "EUR", "euro": "EUR", "euros": "EUR", "eur": "EUR",
            "£": "GBP", "pound": "GBP", "pounds": "GBP", "gbp": "GBP",
            "¥": "JPY", "yen": "JPY", "jpy": "JPY",
            "₹": "INR", "rupee": "INR", "rupees": "INR", "rs": "INR", "rs.": "INR", "inr": "INR"
        }

        found_amount = None
        found_currency = None

        # Check prefix format like "₹500", "rs 500", "rs. 500", "$45", "€ 45"
        prefix_match = re.search(r"(₹|rs\.?|\$|€|£|¥)\s*(\d+(?:\.\d{1,2})?)", msg_lower)
        # Check suffix format like "500 rupees", "500 rs", "45 euros", "50 dollars", "100 usd"
        suffix_match = re.search(r"(\d+(?:\.\d{1,2})?)\s*(rupees?|rs\.?|inr|euros?|eur|dollars?|usd|pounds?|gbp|yen|jpy)", msg_lower)

        if prefix_match:
            sym = prefix_match.group(1).rstrip(".")
            found_currency = currency_map.get(sym, "INR" if sym == "rs" else None)
            found_amount = float(prefix_match.group(2))
        elif suffix_match:
            found_amount = float(suffix_match.group(1))
            word = suffix_match.group(2).rstrip(".")
            found_currency = currency_map.get(word, "INR" if word == "rs" else None)

        # Missing critical information -> ask clarifying question
        if not found_amount or not found_currency:
            if any(w in msg_lower for w in ["paid", "bought", "dinner", "lunch", "coffee", "taxi", "hotel", "ticket", "spent"]):
                return ChatResponse(
                    response="How much did you pay, in which currency, and was this today?",
                    clarification_needed=True,
                    active_trip_id=active_trip.id if active_trip else None
                )
            return ChatResponse(
                response="I'm here to track your travel expenses. You can say 'Paid 45 euros for dinner in Rome' or ask 'How much did I spend on food?'.",
                clarification_needed=False,
                active_trip_id=active_trip.id if active_trip else None
            )

        # Date resolution
        today_val = date.today()
        expense_date = today_val
        if "yesterday" in msg_lower:
            expense_date = today_val - timedelta(days=1)

        city = None
        if active_trip:
            try:
                dests = json.loads(active_trip.destinations)
                for d in dests:
                    if d.lower() in msg_lower:
                        city = d
                        break
            except Exception:
                pass

        split_notes = None
        split_match = re.search(r"split with ([\w\s]+)", msg_lower)
        if split_match:
            split_notes = f"Split with {split_match.group(1).title()}"

        desc = msg

        add_result = cls._tool_add_expense({
            "amount": found_amount,
            "currency": found_currency,
            "description": desc,
            "date": expense_date.strftime("%Y-%m-%d"),
            "city": city,
            "split_notes": split_notes
        }, db, active_trip)

        if "error" in add_result:
            return ChatResponse(response=add_result["error"], clarification_needed=False)

        amt_h = add_result["amount_home"]
        home_cur = add_result["home_currency"]
        cat_disp = add_result["category"].capitalize()
        notes_disp = f" ({split_notes})" if split_notes else ""

        # Currency symbols for display
        cur_symbols = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
        c_sym = cur_symbols.get(found_currency, f"{found_currency} ")
        h_sym = cur_symbols.get(home_cur, f"{home_cur} ")

        anomaly_warn = f" ⚠️ {add_result['anomaly_reason']}" if add_result.get("is_anomaly") else ""
        one_line = f"Saved: {c_sym}{found_amount:.2f} (~{h_sym}{amt_h:.2f}) for {desc} ({cat_disp}) on {expense_date.strftime('%Y-%m-%d')}{notes_disp}.{anomaly_warn}"

        return ChatResponse(
            response=one_line,
            clarification_needed=False,
            tools_called=[ToolExecutionResult(tool="add_expense", arguments={"amount": found_amount, "currency": found_currency}, result=add_result)],
            active_trip_id=active_trip.id if active_trip else None
        )
