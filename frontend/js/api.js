const API_BASE = "/api";

const ApiService = {
  async fetchTrips() {
    const res = await fetch(`${API_BASE}/trips`);
    if (!res.ok) throw new Error("Failed to fetch trips");
    return res.json();
  },

  async fetchActiveTrip() {
    const res = await fetch(`${API_BASE}/trips/active`);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error("Failed to fetch active trip");
    return res.json();
  },

  async createTrip(tripData) {
    const res = await fetch(`${API_BASE}/trips`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(tripData)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to create trip");
    }
    return res.json();
  },

  async fetchExpenses(tripId, category = "", city = "") {
    const params = new URLSearchParams();
    if (tripId) params.append("trip_id", tripId);
    if (category) params.append("category", category);
    if (city) params.append("city", city);

    const res = await fetch(`${API_BASE}/expenses?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to fetch expenses");
    return res.json();
  },

  async deleteExpense(expenseId) {
    const res = await fetch(`${API_BASE}/expenses/${expenseId}`, {
      method: "DELETE"
    });
    if (!res.ok) throw new Error("Failed to delete expense");
    return true;
  },

  async sendChatMessage(message, tripId, history = []) {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, trip_id: tripId, history })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to process message");
    }
    return res.json();
  },

  async uploadReceipt(file, tripId, autoSave = false) {
    const formData = new FormData();
    formData.append("file", file);
    if (tripId) formData.append("trip_id", tripId);
    formData.append("auto_save", autoSave);

    const res = await fetch(`${API_BASE}/receipts/parse`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to parse receipt");
    }
    return res.json();
  },

  async fetchSummary(tripId) {
    const params = tripId ? `?trip_id=${tripId}` : "";
    const res = await fetch(`${API_BASE}/reports/summary${params}`);
    if (!res.ok) throw new Error("Failed to fetch report summary");
    return res.json();
  },

  getExportCsvUrl(tripId) {
    return `${API_BASE}/reports/export${tripId ? `?trip_id=${tripId}` : ""}`;
  },

  async parseSms(smsText, tripId, autoSave = true) {
    const res = await fetch(`${API_BASE}/expenses/parse-sms`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sms_text: smsText, trip_id: tripId, auto_save: autoSave })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to parse SMS");
    }
    return res.json();
  },

  async fetchSettlements(tripId) {
    const res = await fetch(`${API_BASE}/trips/${tripId}/settlements`);
    if (!res.ok) throw new Error("Failed to fetch group settlements");
    return res.json();
  },

  async fetchAnomalies(tripId) {
    const res = await fetch(`${API_BASE}/expenses/anomalies/${tripId}`);
    if (!res.ok) throw new Error("Failed to fetch trip anomalies");
    return res.json();
  }
};
