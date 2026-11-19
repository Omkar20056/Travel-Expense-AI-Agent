let categoryChartInstance = null;
let dailyChartInstance = null;

function formatCurrency(amount, currencyCode) {
  const symbols = {
    INR: "₹",
    USD: "$",
    EUR: "€",
    GBP: "£",
    JPY: "¥",
    CAD: "CA$",
    AUD: "AU$"
  };
  const sym = symbols[currencyCode] || `${currencyCode} `;
  return `${sym}${Number(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const Dashboard = {
  renderSummary(summaryData) {
    if (!summaryData) return;
    const b = summaryData.budget_status;
    const curr = b.home_currency;

    // Metrics
    document.getElementById("valTotalBudget").innerText = formatCurrency(b.total_budget, curr);
    document.getElementById("valTotalSpent").innerText = formatCurrency(b.total_spent_home, curr);
    document.getElementById("valPercentageUsed").innerText = `${b.percentage_used}% of budget`;

    document.getElementById("valRemainingBudget").innerText = formatCurrency(b.remaining_budget, curr);
    document.getElementById("valDaysRemaining").innerText = `${b.days_remaining} days left (${b.trip_days_total} total)`;

    document.getElementById("valDailyAvg").innerText = `${formatCurrency(b.daily_average_spent, curr)}/day`;
    document.getElementById("valDailyTarget").innerText = `Target: ${formatCurrency(b.target_daily_budget, curr)}/day`;

    // Alert Banner
    const banner = document.getElementById("alertBanner");
    const icon = document.getElementById("alertIcon");
    const text = document.getElementById("alertText");

    if (b.is_over_budget) {
      banner.className = "alert-banner danger";
      icon.innerText = "🚨";
      text.innerText = b.warning_message;
      banner.style.display = "flex";
    } else if (b.is_projected_over_budget) {
      banner.className = "alert-banner warning";
      icon.innerText = "⚠️";
      text.innerText = b.warning_message;
      banner.style.display = "flex";
    } else if (b.warning_message) {
      banner.className = "alert-banner success";
      icon.innerText = "✅";
      text.innerText = b.warning_message;
      banner.style.display = "flex";
    } else {
      banner.style.display = "none";
    }

    // Render Charts
    this.renderCategoryChart(summaryData.by_category, curr);
    this.renderDailyChart(summaryData.by_day, curr);
  },

  renderCategoryChart(categories, curr) {
    const ctx = document.getElementById("categoryChart");
    if (!ctx) return;

    if (categoryChartInstance) {
      categoryChartInstance.destroy();
    }

    if (!categories || categories.length === 0) {
      categoryChartInstance = new Chart(ctx, {
        type: "doughnut",
        data: {
          labels: ["No Expenses"],
          datasets: [{ data: [1], backgroundColor: ["#e2e8f0"] }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
      return;
    }

    const labels = categories.map(c => `${c.icon || "📦"} ${c.category.toUpperCase()}`);
    const data = categories.map(c => c.total_amount_home);
    const colors = [
      "#3b82f6", "#10b981", "#f59e0b", "#ec4899",
      "#8b5cf6", "#06b6d4", "#64748b"
    ];

    categoryChartInstance = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: colors.slice(0, categories.length),
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "right" }
        }
      }
    });
  },

  renderDailyChart(days, curr) {
    const ctx = document.getElementById("dailyChart");
    if (!ctx) return;

    if (dailyChartInstance) {
      dailyChartInstance.destroy();
    }

    if (!days || days.length === 0) {
      dailyChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
          labels: ["No Data"],
          datasets: [{ label: "Daily Spend", data: [0], backgroundColor: "#e2e8f0" }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
      return;
    }

    const labels = days.map(d => d.date);
    const data = days.map(d => d.total_amount_home);

    dailyChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: `Spend (${curr})`,
          data: data,
          backgroundColor: "#3b82f6",
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: true }
        }
      }
    });
  },

  renderExpensesTable(expenses, onDeleteCallback) {
    const tbody = document.getElementById("expensesTableBody");
    if (!tbody) return;

    if (!expenses || expenses.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 2rem;">No expenses found.</td></tr>`;
      return;
    }

    tbody.innerHTML = expenses.map(exp => {
      const modeBadge = exp.payment_mode && exp.payment_mode !== "Cash" 
        ? `<span class="badge" style="background:#e0f2fe;color:#0369a1;font-size:0.68rem;padding:2px 6px;margin-left:4px;">${exp.payment_mode}</span>` 
        : "";
      const anomalyBadge = exp.is_anomaly 
        ? `<span class="badge" style="background:#fee2e2;color:#b91c1c;font-size:0.68rem;padding:2px 6px;margin-left:4px;" title="${exp.anomaly_reason || 'Anomaly detected'}">⚠️ Review</span>` 
        : "";

      return `
      <tr>
        <td><strong>${exp.date}</strong></td>
        <td>
          <div style="font-weight: 500;">
            ${exp.description}
            ${modeBadge}
            ${anomalyBadge}
          </div>
          ${exp.merchant ? `<small style="color:var(--text-muted);">${exp.merchant}</small>` : ""}
        </td>
        <td>
          <span class="badge">
            <span>${exp.category_icon || "📦"}</span>
            <span>${exp.category_name}</span>
          </span>
        </td>
        <td>${exp.city || "—"}</td>
        <td>${formatCurrency(exp.amount, exp.currency)}</td>
        <td><strong>${formatCurrency(exp.amount_home, exp.home_currency)}</strong></td>
        <td><small style="color:var(--text-muted);">${exp.split_notes || (exp.paid_by_name ? `Paid by ${exp.paid_by_name}` : "—")}</small></td>
        <td>
          <button class="btn-icon-danger" onclick="window.handleDeleteExpense(${exp.id})">Delete</button>
        </td>
      </tr>
      `;
    }).join("");
  },

  latestWhatsappMessage: "",

  renderSettlements(data) {
    if (!data) return;
    this.latestWhatsappMessage = data.whatsapp_message || "";
    const curr = data.home_currency || "USD";

    // 1. Participant Net Balance Pills
    const pillsContainer = document.getElementById("participantPills");
    if (pillsContainer && data.net_balances) {
      const entries = Object.entries(data.net_balances);
      if (entries.length === 0) {
        pillsContainer.innerHTML = `<span class="pill-balance zero">No group participants yet</span>`;
      } else {
        pillsContainer.innerHTML = entries.map(([person, bal]) => {
          let cls = "zero";
          let label = "Settled";
          if (bal > 0.01) {
            cls = "positive";
            label = `gets back ${formatCurrency(bal, curr)}`;
          } else if (bal < -0.01) {
            cls = "negative";
            label = `owes ${formatCurrency(Math.abs(bal), curr)}`;
          }
          return `<span class="pill-balance ${cls}"><strong>${person}</strong>: ${label}</span>`;
        }).join("");
      }
    }

    // 2. Simplified Debt Transfers
    const listContainer = document.getElementById("debtTransferList");
    if (listContainer) {
      const debts = data.simplified_debts || [];
      if (debts.length === 0) {
        listContainer.innerHTML = `
          <div class="debt-transfer-item" style="color:var(--text-muted); justify-content:center;">
            🎉 All expenses are settled! No pending debt transfers.
          </div>`;
      } else {
        listContainer.innerHTML = debts.map((d, idx) => `
          <div class="debt-transfer-item">
            <div>
              <strong>${idx + 1}. ${d.from_person}</strong> 
              <span style="color:var(--text-muted); margin:0 4px;">➡️ pays</span> 
              <strong>${d.to_person}</strong>
            </div>
            <strong style="color:var(--primary); font-size:0.95rem;">
              ${formatCurrency(d.amount, curr)}
            </strong>
          </div>
        `).join("");
      }
    }
  }
};
