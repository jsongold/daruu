# PRD: Agent-Driven Chat UI — Validation Scenarios

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## Validation Scenarios

> **Note:** The scenarios below were written for an earlier conversational approach.
> The **actual implementation** follows the "Auto-fill first" philosophy:
> 1. User uploads documents
> 2. Agent auto-fills ALL fields without asking questions
> 3. User sees filled preview immediately
> 4. User edits via inline or chat if needed
> 5. User downloads
>
> These scenarios remain for edge case coverage but agent behavior is NON-CONVERSATIONAL.

### Common Cases (Happy Paths)

#### Scenario 1: Government Application with Complex Rules
**Context:** User needs to fill a government benefits application form.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `benefits_application.pdf` | "I analyzed this benefits application form. It has **45 fields**: 12 required, 33 optional. Some fields have rules: - SSN must be XXX-XX-XXXX format - Date of Birth determines eligibility - Income section only required if employed. Do you have source documents, or shall I guide you through the required fields?" |
| 2 | "Guide me through it" | "Let's start with the required fields. **Full Legal Name** (required):" |
| 3 | "John Michael Smith" | "Got it. **Social Security Number** (required, format: XXX-XX-XXXX):" |
| 4 | "123-45-6789" | "Valid SSN. **Date of Birth** (required):" |
| 5 | "March 15, 1985" | "You're 39 years old - eligible for this program. **Current Employment Status** (required):" |
| 6 | "Unemployed" | "Since you're unemployed, I'm skipping the Income section (not required). **Current Address** (required):" |
| 7 | ... (continues for required fields only) | ... |
| 8 | (last required field) | "All 12 required fields complete! The 33 optional fields are left blank (you can fill them later if needed). [Preview] [Approve] [Add Optional Fields]" |

**Validates:** Rule detection, conditional logic, required vs optional handling, format validation.

---

#### Scenario 2: Tax Form with Source Document
**Context:** User has a tax form and a W-2.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `1040.pdf` and `w2.pdf` | "I found: - `1040.pdf`: Tax return form (23 fields, 15 required) - `w2.pdf`: W-2 showing wages of $75,000 from TechCorp Inc. I can auto-fill 10 of the 15 required fields from your W-2. The remaining 5 required fields need your input. Proceed?" |
| 2 | "Yes" | "Filled from W-2: Wages, Employer, EIN, Federal Tax Withheld, etc. Now I need: **Filing Status** (required - Single, Married Filing Jointly, etc.):" |
| 3 | "Married filing jointly" | "Got it. **Spouse's SSN** (required when married):" |
| 4 | "987-65-4321" | "**Number of Dependents** (required):" |
| 5 | "2" | "**Dependent Names and SSNs** (required when dependents > 0):" |
| 6 | "Emma Smith 111-22-3333, Jack Smith 444-55-6666" | "All required fields complete! [Preview] I left optional fields blank (charitable contributions, itemized deductions, etc.). Want to add any?" |
| 7 | "No, that's fine" | "[Download PDF]" |

**Validates:** Source document extraction, conditional required fields, smart field skipping.

---

#### Scenario 3: Simple Application (Few Required Fields)
**Context:** User has a membership application where most fields are optional.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `membership_form.pdf` | "This membership form has 15 fields but only **3 are required**: Name, Email, and Signature Date. The rest (phone, address, interests, referral source, etc.) are optional. Want to fill just the required fields, or all of them?" |
| 2 | "Just required" | "**Full Name** (required):" |
| 3 | "Sarah Johnson" | "**Email** (required):" |
| 4 | "sarah@email.com" | "**Today's Date** for signature (required) - I'll use January 30, 2024. OK?" |
| 5 | "Yes" | "Done! Only 3 fields filled, 12 left blank (all optional). [Preview] [Download]" |

**Validates:** Minimal interaction for simple forms, clear required/optional distinction.

---

#### Scenario 4: Chat-Based Form Filling (No Document Upload)
**Context:** User describes what they need via chat, agent generates the filled form.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | "I need to fill out a W-9 form for my freelance work" | "I can help you fill a W-9 form. I'll ask for the required information: **Legal Name** (as shown on your tax return):" |
| 2 | "Sarah Johnson" | "**Business Name** (if different from above, or leave blank):" |
| 3 | "Leave it blank" | "**Tax Classification** (Individual, LLC, Corporation, etc.):" |
| 4 | "Individual" | "**Address** (number, street, apt):" |
| 5 | "123 Main St, Apt 4B" | "**City, State, ZIP**:" |
| 6 | "New York, NY 10001" | "**SSN or EIN** (for tax identification):" |
| 7 | "123-45-6789" | "All required fields complete! Generating your W-9... [Preview] The signature and date fields are left for you to sign by hand. [Download PDF]" |

**Validates:** No source document needed, agent knows form structure, guided input.

---

#### Scenario 5: Multiple Source Documents
**Context:** User has a loan application and multiple supporting documents.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `loan_app.pdf`, `paystub.pdf`, `bank_stmt.pdf`, `tax_return.pdf` | "I found a loan application and 3 source documents. Let me analyze... - **Loan Application**: 35 fields, 18 required - **Paystub**: Monthly income $6,500, Employer: TechCorp - **Bank Statement**: Balance $24,000, Account ending 1234 - **Tax Return**: 2023 AGI $78,000. I can auto-fill 15 of 18 required fields. Proceed?" |
| 2 | "Yes" | "Filled: Income ($6,500/mo), Employer (TechCorp), Assets ($24,000), Annual Income ($78,000 from tax return). **3 required fields need your input**: Loan Amount, Loan Purpose, Co-Applicant (Yes/No):" |
| 3 | "$50,000 for home renovation, no co-applicant" | "Perfect. All required fields complete! [Preview] Optional fields left blank: Previous Addresses, Additional Income Sources, References. Add any?" |
| 4 | "No" | "[Download PDF]" |

**Validates:** Multi-document aggregation, intelligent field mapping, minimal user input.

---

#### Scenario 6: Generate Document from User Input Only
**Context:** User wants to fill a form purely from chat, no documents uploaded.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | "I need to create an invoice for my client" | "I'll help you create an invoice. I need some information: **Your Business Name**:" |
| 2 | "Smith Consulting" | "**Client Name**:" |
| 3 | "Acme Corporation" | "**Invoice Items** (describe each service/product with amount):" |
| 4 | "Web design $2,000, Logo design $500" | "**Payment Terms** (due date or net days):" |
| 5 | "Net 30" | "**Your Contact Info** (for the invoice header):" |
| 6 | "john@smithconsulting.com, 555-1234" | "Here's your invoice: - Smith Consulting → Acme Corporation - Web design: $2,000 - Logo design: $500 - **Total: $2,500** - Due: 30 days from today [Preview] [Download PDF]" |

**Validates:** Pure chat-based document generation, no form upload required.

---

#### Scenario 7: Batch Processing with Template (Power User)
**Context:** HR user needs to generate the same form for multiple employees.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `offer_letter_template.pdf` | "I see an offer letter template with fields: Employee Name, Position, Salary, Start Date, Manager Name. Would you like to: (1) Fill for one person, or (2) **Batch fill** for multiple people?" |
| 2 | "Batch fill for 3 people" | "Great! I'll collect info for each person. **Person 1 - Employee Name**:" |
| 3 | "Alice Johnson" | "**Position**:" |
| 4 | "Software Engineer" | "**Salary**:" |
| 5 | "$120,000" | "**Start Date**:" |
| 6 | "Feb 15, 2024" | "**Manager Name**:" |
| 7 | "Bob Smith" | "Person 1 complete! **Person 2 - Employee Name**:" |
| 8 | ... (repeats for persons 2 and 3) | ... |
| 9 | (all 3 complete) | "3 offer letters ready: - Alice Johnson - Software Engineer - $120k - Carol Davis - Product Manager - $140k - David Lee - Designer - $100k. [Download All as ZIP] [Download Individual PDFs]" |

**Validates:** Template reuse, batch processing, multiple output files.

---

#### Scenario 8: Reuse Previous Data (Saved Profile)
**Context:** Returning user who has filled similar forms before.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops new `rental_application.pdf` | "I see a rental application. I notice you've filled similar forms before. Your saved info: - Name: John Smith - SSN: XXX-XX-6789 - Current Address: 123 Main St - Employer: TechCorp. **Use this saved data?**" |
| 2 | "Yes, but update address to 456 Oak Ave" | "Got it! Using saved profile with new address. Filling form... The form also asks for **Monthly Income** and **Landlord Reference** - not in your profile. **Monthly Income**:" |
| 3 | "$6,500" | "**Landlord Reference** (name and phone):" |
| 4 | "Jane Doe, 555-9876" | "All fields complete! [Preview] Your profile has been updated with new address. [Download PDF]" |

**Validates:** Profile/data reuse, incremental updates, returning user experience.

---

### Complex Form Scenarios

#### Complex 1: Multi-Page Form with Sections
**Context:** User has a 10-page insurance application with different sections. *(See [agent-chat-ui.md](../agent-chat-ui.md) for full step table.)*

**Validates:** Multi-page navigation, section-based filling, conditional section skipping.

#### Complex 2: Form Requiring Attachments
**Context:** Visa application that requires photo and supporting documents. *(See full PRD for table.)*

**Validates:** Attachment handling, file validation, package generation.

#### Complex 3: Form with Digital Signature
**Context:** Contract that requires electronic signature. *(See full PRD for table.)*

**Validates:** Signature fields, multiple signature methods, date auto-fill.

#### Complex 4: Form with Calculations
**Context:** Expense report that requires totals and tax calculations. *(See full PRD for table.)*

**Validates:** Auto-calculation, itemized entry, tax rules.

#### Complex 5: Form with Conditional Pages
**Context:** Business license application where pages depend on business type. *(See full PRD for table.)*

**Validates:** Conditional page logic, dynamic form sections, clear skip explanations.

#### Complex 6: Non-AcroForm PDF (Scanned/Flat Form)
**Context:** User uploads a PDF with no interactive form fields. Agent uses vision LLM for bbox detection and text overlay.

**Validates:** Bbox detection, text overlay positioning, non-AcroForm handling.

#### Complex 7: Image as Form (JPG/PNG)
**Context:** User uploads an image of a form. **Validates:** Image input, image-to-PDF conversion, bbox detection on images.

#### Complex 8: Mixed Documents (Image Source + PDF Form)
**Context:** PDF form + photo of receipt as source. **Validates:** Image as source, OCR, mixed document types.

---

### Edge Cases

#### Edge Case 1: Conflicting Data from Multiple Sources
Agent detects conflict (e.g. two paystubs, different employers), asks user to resolve.

#### Edge Case 2: Invalid Format Correction
User provides wrong format (e.g. SSN without dashes); agent suggests correction, does not block.

#### Edge Case 3: Unknown Form Type
Agent falls back to fields marked (*) as required when form type is unrecognized.

#### Edge Case 4: Partial Extraction from Poor Quality Scan
Agent reports low-confidence fields, asks user to confirm (e.g. blurry W-2).

---

### Scope-Out Cases (Explicitly NOT Supported)

| Out of Scope | Agent Response / Alternative |
|--------------|------------------------------|
| **Form Creation/Design** | "I help fill existing forms." Use Adobe Acrobat, JotForm for creation. |
| **Non-PDF/Non-Image Files** | "PDF and image files only. Export spreadsheet to PDF first." |
| **Real-Time Collaboration** | One person per conversation; share preview for review. |
| **Form Submission to Government** | Download and submit via official channels. |
| **Handwriting Recognition** | Use digital form or type values. |
| **Legal/Medical Advice** | Consult professionals; agent only fills values user provides. |
| **Offline Mode** | Internet required for AI processing. |

### Scope-Out Summary

| Feature | Status | Alternative |
|---------|--------|-------------|
| Form creation | ❌ Out | Use Adobe Acrobat, JotForm |
| Non-PDF/Image files | ❌ Out | Export to PDF first |
| Real-time collaboration | ❌ Out | Share preview, make changes sequentially |
| Form submission | ❌ Out | Download and submit manually |
| Handwriting recognition | ❌ Out | Use digital forms or type values |
| Legal/medical advice | ❌ Out | Consult professionals |
| Offline mode | ❌ Out | Requires internet |

### IN Scope: Special Handling

| Feature | Status | How It Works |
|---------|--------|--------------|
| Image files (PNG, JPG, TIFF) | ✅ In | Treated as single-page documents, can be form or source |
| Non-AcroForm PDFs | ✅ In | LLM detects field locations, generates bounding boxes |
| Scanned forms | ✅ In | OCR + bbox generation for text placement |

### Scenario Coverage Matrix

| Scenario | AcroForm | Non-AcroForm | Image | Bbox Gen | OCR |
|----------|----------|--------------|-------|----------|-----|
| Government App | ✓ | | | | |
| Tax Form + W-2 | ✓ | | | | |
| Simple Membership | ✓ | | | | |
| Chat-Based (W-9) | ✓ | | | | |
| Multiple Sources | ✓ | | | | |
| Generate from Chat | ✓ | | | | |
| Batch Template | ✓ | | | | |
| Reuse Profile | ✓ | | | | |
| Multi-Page Sections | ✓ | | | | |
| Form + Attachments | ✓ | | | | |
| Digital Signature | ✓ | | | | |
| Calculations | ✓ | | | | |
| Conditional Pages | ✓ | | | | |
| **Non-AcroForm PDF** | | ✓ | | ✓ | ✓ |
| **Image as Form** | | | ✓ | ✓ | ✓ |
| **Mixed (Image Source)** | ✓ | | ✓ | | ✓ |

### Feature Coverage Summary

| Feature | Scenarios Covering It |
|---------|----------------------|
| AcroForm PDFs | 13 scenarios |
| Non-AcroForm PDFs (flat/scanned) | 1 scenario |
| Image files as form | 1 scenario |
| Image files as source | 1 scenario |
| Bounding Box Generation | 2 scenarios |
| OCR | 3 scenarios |
| Rule Detection | 9 scenarios |
| Required/Optional Fields | 8 scenarios |
| Multi-Page Forms | 4 scenarios |
| Attachments | 1 scenario |
| Digital Signature | 2 scenarios |
| Auto-Calculations | 2 scenarios |
| Conditional Logic | 4 scenarios |
| Batch Processing | 1 scenario |
| User Profile | 1 scenario |
| Source Document Extraction | 5 scenarios |
