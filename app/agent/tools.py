AGENT_TOOLS = [
    {
        "name": "add_expense",
        "description": "Log a new expense for a trip. Automatically handles currency conversion to the trip's home currency based on the transaction date. Do NOT call this tool if amount, currency, or date is ambiguous—ask a clarifying question first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "The exact numeric amount paid in the original currency (e.g., 45.00)."
                },
                "currency": {
                    "type": "string",
                    "description": "3-letter ISO 4217 currency code (e.g., 'EUR', 'USD', 'JPY', 'GBP')."
                },
                "description": {
                    "type": "string",
                    "description": "Short description of the expense (e.g., 'Dinner with pasta and wine')."
                },
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "Date of expense in YYYY-MM-DD format. Resolve relative expressions like 'today' or 'yesterday' against the system date."
                },
                "category": {
                    "type": "string",
                    "enum": ["food", "transport", "lodging", "activities", "shopping", "fees", "other"],
                    "description": "Optional category. If omitted, the backend will auto-classify using learned rules and merchant matching."
                },
                "merchant": {
                    "type": "string",
                    "description": "Name of the merchant, restaurant, airline, or shop if known (e.g., 'Trattoria Da Enzo')."
                },
                "city": {
                    "type": "string",
                    "description": "City where the expense took place (e.g., 'Rome', 'Paris')."
                },
                "split_notes": {
                    "type": "string",
                    "description": "Any split details mentioned (e.g., 'Split with Sam', 'Paid for 3 people')."
                },
                "trip_id": {
                    "type": "integer",
                    "description": "ID of the trip. If omitted, the active trip is used."
                }
            },
            "required": ["amount", "currency", "description", "date"]
        }
    },
    {
        "name": "edit_expense",
        "description": "Modify an existing expense by ID. If correcting a category, set learn_category_rule to true so future expenses with similar merchant/keyword learn the correction.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expense_id": {
                    "type": "integer",
                    "description": "The unique ID of the expense to update."
                },
                "amount": {
                    "type": "number",
                    "description": "Updated amount in original currency."
                },
                "currency": {
                    "type": "string",
                    "description": "Updated 3-letter currency code."
                },
                "category": {
                    "type": "string",
                    "enum": ["food", "transport", "lodging", "activities", "shopping", "fees", "other"],
                    "description": "Updated category."
                },
                "description": {
                    "type": "string",
                    "description": "Updated description."
                },
                "merchant": {
                    "type": "string",
                    "description": "Updated merchant name."
                },
                "city": {
                    "type": "string",
                    "description": "Updated city."
                },
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "Updated date in YYYY-MM-DD format."
                },
                "split_notes": {
                    "type": "string",
                    "description": "Updated split notes."
                },
                "learn_category_rule": {
                    "type": "boolean",
                    "description": "Set to true when user explicitly corrects a category (e.g., 'Starbucks is food, not shopping'), saving this rule for future auto-categorizations."
                }
            },
            "required": ["expense_id"]
        }
    },
    {
        "name": "delete_expense",
        "description": "Delete an expense by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expense_id": {
                    "type": "integer",
                    "description": "The ID of the expense to delete."
                }
            },
            "required": ["expense_id"]
        }
    },
    {
        "name": "list_expenses",
        "description": "Search or retrieve a list of logged expenses filtered by trip, category, city, or date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_id": {
                    "type": "integer",
                    "description": "Trip ID. Defaults to active trip if omitted."
                },
                "category": {
                    "type": "string",
                    "enum": ["food", "transport", "lodging", "activities", "shopping", "fees", "other"],
                    "description": "Filter by category."
                },
                "city": {
                    "type": "string",
                    "description": "Filter by city (e.g., 'Paris', 'Rome')."
                },
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Start of date range (YYYY-MM-DD)."
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "End of date range (YYYY-MM-DD)."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records to return (default: 20)."
                }
            }
        }
    },
    {
        "name": "get_summary",
        "description": "Get spending summaries and budget tracking analytics. Returns total spent, remaining budget, daily average burn rate, projected overspend warnings, and breakdowns by category, day, or city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_id": {
                    "type": "integer",
                    "description": "Trip ID. Defaults to active trip if omitted."
                },
                "group_by": {
                    "type": "string",
                    "enum": ["overall", "category", "day", "city"],
                    "description": "Aggregation level. 'overall' returns total vs budget & projections; others return specific groupings."
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter (e.g., 'food' to answer 'How much did I spend on food in Paris?')."
                },
                "city": {
                    "type": "string",
                    "description": "Optional city filter (e.g., 'Paris')."
                }
            }
        }
    },
    {
        "name": "convert_currency",
        "description": "Convert an amount between currencies using historical or latest exchange rates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "Amount to convert."
                },
                "from_currency": {
                    "type": "string",
                    "description": "Source 3-letter currency code (e.g., 'EUR')."
                },
                "to_currency": {
                    "type": "string",
                    "description": "Target 3-letter currency code (e.g., 'USD')."
                },
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "Historical date (YYYY-MM-DD). If omitted, latest available rate is used."
                }
            },
            "required": ["amount", "from_currency", "to_currency"]
        }
    },
    {
        "name": "set_budget",
        "description": "Update or set the total budget and/or home currency for a trip.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_id": {
                    "type": "integer",
                    "description": "Trip ID. Defaults to active trip if omitted."
                },
                "total_budget": {
                    "type": "number",
                    "description": "New total budget amount in trip's home currency."
                },
                "home_currency": {
                    "type": "string",
                    "description": "3-letter currency code (e.g., 'USD')."
                }
            }
        }
    },
    {
        "name": "parse_receipt",
        "description": "Process an uploaded receipt image or document, extracting merchant, date, total amount, currency, and line items.",
        "input_schema": {
            "type": "object",
            "properties": {
                "receipt_id": {
                    "type": "string",
                    "description": "Identifier or temporary path of the uploaded receipt file."
                },
                "trip_id": {
                    "type": "integer",
                    "description": "Trip ID to associate with. Defaults to active trip if omitted."
                },
                "auto_save": {
                    "type": "boolean",
                    "description": "If true, automatically creates the expense record upon successful extraction. If false, returns extracted details for user confirmation."
                }
            },
            "required": ["receipt_id"]
        }
    },
    {
        "name": "parse_payment_sms",
        "description": "Parse raw payment notification SMS, UPI alerts (Google Pay, PhonePe, Paytm), or credit/debit card alerts into structured expense data and automatically log it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sms_text": {
                    "type": "string",
                    "description": "The full raw text of the payment SMS or transaction alert."
                },
                "trip_id": {
                    "type": "integer",
                    "description": "Trip ID to associate with. Defaults to active trip if omitted."
                }
            },
            "required": ["sms_text"]
        }
    },
    {
        "name": "get_group_settlements",
        "description": "Calculate who owes whom in the trip, compute net balances for each traveler, and generate simplified minimal debt settlement transfers (Splitwise-style) with a WhatsApp-ready summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_id": {
                    "type": "integer",
                    "description": "Trip ID. Defaults to active trip if omitted."
                }
            }
        }
    },
    {
        "name": "check_spending_anomalies",
        "description": "Scan trip expenses for duplicates, potential double swipes, unusual category price spikes, and budget hazards.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_id": {
                    "type": "integer",
                    "description": "Trip ID. Defaults to active trip if omitted."
                }
            }
        }
    }
]
