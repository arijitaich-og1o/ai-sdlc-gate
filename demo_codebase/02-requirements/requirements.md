# Product Requirements — Customer Self-Service Returns Portal

Version 0.3 (draft, but development has started)

## 1. Overview

Customers should be able to return items themselves instead of calling support. The portal must be fast,
user-friendly and work on all devices.

## 2. User stories

### US-1 Start a return
As a customer I want to start a return so that I get my money back.

**Acceptance criteria**
- The return flow works correctly.
- The customer is happy with the experience.

### US-2 Upload photos
As a customer I want to upload photos of the damaged item.

**Acceptance criteria**
- Photos can be uploaded.
- Large photos are handled appropriately.

### US-3 Refund
As a customer I want the refund quickly.

**Acceptance criteria**
- Refunds are processed within a reasonable time.
- The refund amount is correct.

### US-4 Admin export
As a support agent I want to export all returns with customer details to Excel so that I can analyse them.

**Acceptance criteria**
- Clicking "Export" downloads all returns, including customer name, address, phone number, date of birth and
  the last four digits of the card, etc.

### US-5 Identity check
To prevent fraud, customers must provide their date of birth and government ID number when returning items above
INR 5,000. This data is stored with the return.

## 3. Business rules

- BR-1: Returns are accepted within 30 days of delivery.
- BR-2: Returns of electronics are accepted within 15 days of delivery.
- BR-3: Returns are accepted within 45 days for Loyalty Gold members regardless of category.
- BR-4: Return data is retained for 30 days after the refund is issued.
- BR-5: Return data must be retained indefinitely for audit purposes.
- BR-6: The service must use MongoDB and be written in Node.js.

## 4. Non-functional requirements

- The system should be fast.
- The system should be secure.
- Availability: high.

## 5. Open items

- Refund method for cash-on-delivery orders: TBD.
- What happens when a photo upload fails half-way: TODO.
- Who can access the admin export: to be decided later.
