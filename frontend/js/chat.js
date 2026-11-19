const Chat = {
  history: [],

  init(onRefreshDashboard) {
    this.onRefreshDashboard = onRefreshDashboard;
    const form = document.getElementById("chatForm");
    const input = document.getElementById("chatInput");
    const dropzone = document.getElementById("receiptDropzone");
    const fileInput = document.getElementById("receiptFileInput");

    // Chat submit
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;

      input.value = "";
      await this.sendMessage(text);
    });

    // Quick chips
    document.querySelectorAll(".chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const prompt = chip.getAttribute("data-prompt");
        if (prompt) {
          this.sendMessage(prompt);
        }
      });
    });

    // Receipt click & drag-and-drop
    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", async (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        await this.handleReceiptUpload(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", async (e) => {
      if (e.target.files && e.target.files.length > 0) {
        await this.handleReceiptUpload(e.target.files[0]);
        fileInput.value = "";
      }
    });

    // Voice Input Microphone
    this.initVoiceInput(input);

    // SMS Modal handlers
    this.initSmsModal();

    // WhatsApp Copy handler
    this.initWhatsAppCopy();
  },

  initVoiceInput(inputElement) {
    const btnVoice = document.getElementById("btnVoiceInput");
    if (!btnVoice) return;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      btnVoice.title = "Voice recognition not supported in this browser";
      btnVoice.style.opacity = "0.5";
      btnVoice.addEventListener("click", () => alert("Web Speech API is not supported in this browser. Please use Google Chrome or Edge."));
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    let isListening = false;

    btnVoice.addEventListener("click", () => {
      if (isListening) {
        recognition.stop();
        return;
      }
      try {
        recognition.start();
        isListening = true;
        btnVoice.classList.add("listening");
        btnVoice.title = "Listening... Speak your expense";
      } catch (err) {
        console.error("Speech recognition error:", err);
      }
    });

    recognition.onresult = (event) => {
      const speechResult = event.results[0][0].transcript;
      inputElement.value = speechResult;
      btnVoice.classList.remove("listening");
      isListening = false;
      this.sendMessage(speechResult);
      inputElement.value = "";
    };

    recognition.onerror = (event) => {
      btnVoice.classList.remove("listening");
      isListening = false;
      console.warn("Speech recognition error:", event.error);
    };

    recognition.onend = () => {
      btnVoice.classList.remove("listening");
      isListening = false;
    };
  },

  initSmsModal() {
    const modal = document.getElementById("smsModal");
    const openBtn = document.getElementById("btnOpenSmsModal");
    const cancelBtn = document.getElementById("btnCancelSmsModal");
    const form = document.getElementById("smsForm");
    const smsInput = document.getElementById("smsText");

    if (!modal || !openBtn) return;

    openBtn.addEventListener("click", () => {
      modal.classList.add("active");
      smsInput.focus();
    });

    cancelBtn.addEventListener("click", () => {
      modal.classList.remove("active");
      smsInput.value = "";
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = smsInput.value.trim();
      if (!text) return;

      modal.classList.remove("active");
      smsInput.value = "";

      this.appendMessage("user", `📱 Pasted SMS:\n"${text}"`);

      try {
        const tripId = window.getActiveTripId ? window.getActiveTripId() : null;
        const res = await ApiService.parseSms(text, tripId, true);
        if (res.success && res.expense) {
          const exp = res.expense;
          let reply = `✅ **SMS Transaction Logged!**\n• Merchant: ${exp.merchant || "Vendor"}\n• Amount: ${exp.currency} ${exp.amount.toFixed(2)} (~${exp.home_currency} ${exp.amount_home.toFixed(2)})\n• Category: ${exp.category_name.toUpperCase()}\n• Mode: ${exp.payment_mode || "UPI"}`;
          if (exp.reference_id) reply += `\n• Ref ID: ${exp.reference_id}`;
          if (exp.is_anomaly) reply += `\n⚠️ *Alert:* ${exp.anomaly_reason}`;

          this.appendMessage("agent", reply);
          if (this.onRefreshDashboard) this.onRefreshDashboard();
        } else {
          this.appendMessage("agent", `⚠️ Could not parse SMS: ${res.error || "Missing amount/merchant"}`);
        }
      } catch (err) {
        this.appendMessage("agent", `⚠️ Error parsing SMS: ${err.message}`);
      }
    });
  },

  initWhatsAppCopy() {
    const copyBtn = document.getElementById("btnCopyWhatsApp");
    if (!copyBtn) return;

    copyBtn.addEventListener("click", () => {
      const msg = Dashboard.latestWhatsappMessage;
      if (!msg) {
        alert("No group settlements available to copy yet.");
        return;
      }
      navigator.clipboard.writeText(msg).then(() => {
        const originalText = copyBtn.innerText;
        copyBtn.innerText = "✅ Copied to Clipboard!";
        setTimeout(() => copyBtn.innerText = originalText, 2500);
      }).catch(err => {
        alert("Failed to copy message: " + err);
      });
    });
  },

  appendMessage(role, text, isClarification = false) {
    const container = document.getElementById("chatHistory");
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role} ${isClarification ? "clarification" : ""}`;
    bubble.innerHTML = text.replace(/\n/g, "<br>");
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;

    this.history.push({ role, content: text });
    if (this.history.length > 15) {
      this.history.shift();
    }
  },

  async sendMessage(userText) {
    this.appendMessage("user", userText);

    // Indicator
    const typingIndicator = document.createElement("div");
    typingIndicator.className = "chat-bubble agent";
    typingIndicator.id = "typingIndicator";
    typingIndicator.innerText = "Thinking...";
    document.getElementById("chatHistory").appendChild(typingIndicator);

    try {
      const tripId = window.getActiveTripId ? window.getActiveTripId() : null;
      const resp = await ApiService.sendChatMessage(userText, tripId, this.history.slice(0, -1));

      // Remove typing indicator
      const ind = document.getElementById("typingIndicator");
      if (ind) ind.remove();

      this.appendMessage("agent", resp.response, resp.clarification_needed);

      // Refresh dashboard if tool was called (e.g. expense added/edited)
      if (resp.tools_called && resp.tools_called.length > 0) {
        if (this.onRefreshDashboard) this.onRefreshDashboard();
      }
    } catch (err) {
      const ind = document.getElementById("typingIndicator");
      if (ind) ind.remove();
      this.appendMessage("agent", `⚠️ Error: ${err.message}`, true);
    }
  },

  async handleReceiptUpload(file) {
    const preview = document.getElementById("receiptPreviewName");
    preview.innerText = `Uploading ${file.name}...`;

    this.appendMessage("user", `📸 Uploaded receipt: ${file.name}`);

    try {
      const tripId = window.getActiveTripId ? window.getActiveTripId() : null;
      // Auto-save parsed expense
      const res = await ApiService.uploadReceipt(file, tripId, true);
      preview.innerText = "";

      const parsed = res.result.parsed;
      const saved = res.result.saved_expense;

      let reply = `✅ **Receipt Processed:**\nMerchant: ${parsed.merchant || "Unknown"}\nDate: ${parsed.date || "Today"}\nAmount: ${parsed.currency} ${parsed.amount}`;
      if (saved && saved.success) {
        reply += `\n*Saved to expenses!* (~${saved.home_currency} ${saved.amount_home.toFixed(2)})`;
      }

      this.appendMessage("agent", reply);
      if (this.onRefreshDashboard) this.onRefreshDashboard();
    } catch (err) {
      preview.innerText = "";
      this.appendMessage("agent", `⚠️ Failed to parse receipt: ${err.message}`, true);
    }
  }
};
