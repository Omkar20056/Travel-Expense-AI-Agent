let currentTrip = null;

window.getActiveTripId = () => currentTrip ? currentTrip.id : null;

window.handleDeleteExpense = async (expenseId) => {
  if (!confirm("Are you sure you want to delete this expense?")) return;
  try {
    await ApiService.deleteExpense(expenseId);
    refreshDashboard();
  } catch (err) {
    alert(`Failed to delete expense: ${err.message}`);
  }
};

async function refreshDashboard() {
  if (!currentTrip) return;

  try {
    // 1. Fetch summary analytics
    const summary = await ApiService.fetchSummary(currentTrip.id);
    Dashboard.renderSummary(summary);

    // 2. Fetch expenses list with active filters
    const catFilter = document.getElementById("filterCategory").value;
    const cityFilter = document.getElementById("filterCity").value.trim();
    const expenses = await ApiService.fetchExpenses(currentTrip.id, catFilter, cityFilter);
    Dashboard.renderExpensesTable(expenses);

    // 3. Fetch group debt settlements
    try {
      const settlements = await ApiService.fetchSettlements(currentTrip.id);
      Dashboard.renderSettlements(settlements);
    } catch (sErr) {
      console.warn("Settlements fetch notice:", sErr);
    }

    // Update active trip badge
    document.getElementById("activeTripNameBadge").innerText = `${currentTrip.name} (${currentTrip.home_currency})`;
  } catch (err) {
    console.error("Dashboard refresh error:", err);
  }
}

async function loadTrips() {
  const tripSelect = document.getElementById("tripSelect");
  tripSelect.innerHTML = "";

  let trips = await ApiService.fetchTrips();

  // If no trip exists yet, create an initial default trip for convenience
  if (trips.length === 0) {
    const today = new Date();
    const end = new Date();
    end.setDate(today.getDate() + 14);

    const defaultTrip = {
      name: "European Vacation",
      start_date: today.toISOString().split("T")[0],
      end_date: end.toISOString().split("T")[0],
      destinations: ["Rome", "Paris", "Amsterdam"],
      total_budget: 3000.0,
      home_currency: "USD",
      primary_traveler_name: "Me"
    };
    const created = await ApiService.createTrip(defaultTrip);
    trips = [created];
  }

  trips.forEach(t => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.innerText = `${t.name} (${t.home_currency})`;
    tripSelect.appendChild(opt);
  });

  currentTrip = trips[0];
  tripSelect.value = currentTrip.id;

  tripSelect.addEventListener("change", (e) => {
    const selectedId = parseInt(e.target.value);
    currentTrip = trips.find(t => t.id === selectedId) || trips[0];
    refreshDashboard();
  });

  await refreshDashboard();
}

document.addEventListener("DOMContentLoaded", async () => {
  // Initialize Chat
  Chat.init(() => refreshDashboard());

  // Filters
  document.getElementById("filterCategory").addEventListener("change", () => refreshDashboard());
  document.getElementById("filterCity").addEventListener("input", () => refreshDashboard());

  // Export CSV
  document.getElementById("btnExportCsv").addEventListener("click", () => {
    if (currentTrip) {
      window.location.href = ApiService.getExportCsvUrl(currentTrip.id);
    }
  });

  // Modal handlers
  const modal = document.getElementById("newTripModal");
  document.getElementById("btnNewTrip").addEventListener("click", () => {
    modal.classList.add("active");
  });

  document.getElementById("btnCancelModal").addEventListener("click", () => {
    modal.classList.remove("active");
  });

  document.getElementById("newTripForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("tripName").value;
    const destStr = document.getElementById("tripDestinations").value;
    const start_date = document.getElementById("tripStartDate").value;
    const end_date = document.getElementById("tripEndDate").value;
    const total_budget = parseFloat(document.getElementById("tripBudget").value);
    const home_currency = document.getElementById("tripCurrency").value;

    const destinations = destStr.split(",").map(d => d.trim()).filter(Boolean);

    try {
      const created = await ApiService.createTrip({
        name,
        destinations,
        start_date,
        end_date,
        total_budget,
        home_currency
      });
      modal.classList.remove("active");
      document.getElementById("newTripForm").reset();
      await loadTrips();
      // Select newly created trip
      const select = document.getElementById("tripSelect");
      select.value = created.id;
      currentTrip = created;
      await refreshDashboard();
    } catch (err) {
      alert(`Error creating trip: ${err.message}`);
    }
  });

  // Load initial trips and dashboard
  await loadTrips();
});
