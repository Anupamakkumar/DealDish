# DealDish — surplus food marketplace

A Flask + SQLite web application based on the supplied DealDish project documentation. It connects customers with time-limited surplus-food listings from hotels/restaurants and includes customer, hotel-partner and administrator workflows.

## Features
- Responsive, mobile-friendly marketplace with search, category filters, deal expiry, stock and discounted pricing.
- Customer and hotel registration/login with password hashing and role-based access.
- Hotel registration captures a 12-digit FSSAI number; admin review (pending/approved/rejected) controls listing access. Approved partners are shown as FSSAI-reviewed/verified within DealDish. **This is a workflow for manual review, not a live FSSAI registry/API verification.**
- Hotel portal: create and hide deals, manage price/quantity/expiry, see orders and update fulfilment status.
- Customer basket, checkout, pickup/delivery selection, cash/demo payment choices, order history and reward points.
- Customer order cancellation while the order is still Placed or Confirmed; stock is restored once and online-demo payments are marked for manual refund processing.
- Admin refund tracking: administrators can mark a pending refund as processed after completing the actual transfer through the payment provider.
- Separate 1–5 star food and hotel ratings with written feedback, limited to completed orders; customers see ratings on deal pages and hotels can review their feedback in the hotel portal.
- In-app customer/hotel/admin notifications for hotel applications, new orders, cancellations, order-status changes, refund updates and reviews.
- Admin console to review hotels, moderate deals, and inspect users/orders.
- Optional nearby-deal API using saved hotel coordinates and browser geolocation. Demo hotels do not have coordinates by default, so nearby search needs real coordinates to be entered in the database.
- Seeded demo deals so the interface is populated on first run.

## Run on Windows
1. Install Python 3.10+ (Python 3.12 is fine).
2. Extract this ZIP.
3. Open PowerShell/Command Prompt in the extracted `DealDish` folder.
4. Run:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python app.py
   ```
5. Open `http://127.0.0.1:5000` in your browser.

You can also double-click `run_windows.bat` if Python is available as `python` on PATH.

## Demo accounts
- **Admin:** `admin@dealdish.local` / `Admin@123`
- **Demo hotel accounts:** `demo0@dealdish.local` through `demo5@dealdish.local` / `Demo@123`
- Create a customer account through the registration page.

Demo hotel listings are seeded as approved to make the customer marketplace immediately usable. New hotel registrations remain pending until admin review.

## Database and configuration
- SQLite database `dealdish.db` is created automatically on first run and excluded from the ZIP. Existing databases are preserved: startup performs additive column migrations for cancellation/refund and hotel-rating fields; do not delete your existing database.
- Set environment variable `SECRET_KEY` before deployment. The included key is for local development only.
- For a real deployment, disable debug mode, use HTTPS, configure a production server, add CSRF protection and rate limiting, validate uploaded assets, use a production database, and integrate a real payment provider and trusted delivery workflow.

## Important demo limitations
- “Online payment (demo)” does not charge money. No payment gateway is integrated. Refunds are therefore tracked for manual processing only; “Mark refunded” records that an administrator says the transfer has been completed and does not send money.
- Delivery is a selectable order workflow, not a live courier integration. The address is collected in the checkout form but is not yet persisted to the order record.
- FSSAI numbers are format-validated and reviewed manually; no official FSSAI API is connected.
- Browser geolocation requires user permission and a secure context (localhost is normally allowed). Nearby results only include hotels with stored latitude/longitude.
- Reward points are a simple demonstration ledger balance, not a redeemable currency.
- Sample food photos are loaded from Unsplash over the internet.

## Main structure
```
DealDish/
├── app.py
├── requirements.txt
├── run_windows.bat
├── README.md
├── templates/     # Jinja HTML pages
└── static/        # CSS and JavaScript
```
