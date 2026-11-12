# Fuel Desk

A fuel purchasing application built with Django, Django REST Framework, Jinja2 and SQLite. Requires Python 3.10+ or Docker with Compose.

## Run with Docker

```bash
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

Open http://127.0.0.1:8000/login/ and sign in with the username and password you chose. Create the administrator once. Port 8000 must be available.

Migrations and static file collection run at startup. The fuel-web-data volume persists the database and generated Django secret across container restarts. The container uses Django's development server.

```bash
docker compose exec web python manage.py test
docker compose logs -f web
docker compose down
```

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py runserver 8000
```

## Roles and authentication

Administrators manage fuel, users and balances and see all purchases. Customers see their own balance and purchase history and can buy fuel.

Sign-in uses Django sessions. Passwords are hashed, and modifying browser requests require CSRF tokens. Sign-out accepts POST.

When creating a customer under Users, set a password and starting balance. Editing a balance sets the final amount. Leaving the password blank on an existing account keeps its current password.

## Pages

| Address | Purpose |
| --- | --- |
| /login/ | Sign in |
| / | Overview and balance |
| /products/ | Fuel catalogue |
| /products/new/ | Add fuel, administrator only |
| /products/{id}/edit/ | Edit price and stock, administrator only |
| /products/{id}/buy/ | Buy fuel |
| /users/ | Users and balances, administrator only |
| /users/new/ | Create a customer account |
| /users/{id}/edit/ | Edit customer details, balance and password |
| /purchases/ | All purchases for administrators, own purchases for customers |
| /logout/ | Sign out using POST |

## API

POST /api/admin/products/ and /api/admin/users/ create records. PATCH /api/admin/products/{id}/ and /api/admin/users/{id}/ update them.

Management endpoints accept a staff JWT, an authenticated staff session with CSRF protection, or an X-Admin-Key generated with `python manage.py create_admin operator`. The API administrator key and web administrator account are created separately.

GET and POST /api/purchases/ accept a customer JWT or an authenticated customer session. X-Username does not select the customer. Session-based POST requests require the session cookie, CSRF cookie and X-CSRFToken header. JWT requests use Authorization: Bearer <access>. Example body follows.

```json
{"product_id": 1, "litres": "10.00"}
```

For users created through the API, set a password in the web interface to enable sign-in.

Money and litres use two decimal places. Purchase totals use ROUND_HALF_UP rounding. Purchases and management updates use SQLite IMMEDIATE transactions.

## Configuration

Django authentication accounts link to customers through User.account. The separate Admin model stores hashed API keys.

FUEL_DATA_DIR sets the database and secret directory. DJANGO_SECRET_KEY can supply a secret through the environment. Otherwise a secret is generated once and saved to .secret_key, which is excluded from Git and the Docker image.

The web application uses its own database. Add demonstration data through the interface.

## Demonstration walkthrough

1. Sign in as the administrator and open Overview. Explain the stock, customer and purchase totals.
2. Open Fuel, select Add fuel and create Petrol 95 with a price of 500.00 and stock of 1000.00 litres. Use a fresh product for each demonstration.
3. Select Edit on that product and change its stock to 1200.00 litres. Show that the new value appears in the catalogue.
4. Open Users and create a customer with a unique username, first and last name, a valid birthdate, a strong password and a balance of 0.00.
5. Edit that customer and set the balance to 10000.00. Explain that this sets the final balance.
6. Sign out and sign in as the customer. Show the 10000.00 balance and fuel catalogue.
7. Buy 10.00 litres of the new product. The purchase costs 5000.00. Show the record in Purchases, the remaining 5000.00 balance in Overview and the 1190.00-litre stock in Fuel.
8. Try buying 11.00 litres. Show the insufficient balance error. Try 1200.00 litres to show the insufficient stock error. Confirm that the balance, stock and purchase count are unchanged.
9. While signed in as the customer, open /users/ directly. Show the 403 response demonstrating server-side access control.
10. Sign out and sign back in as the administrator. Show the customer's updated balance and the purchase in the full history.
11. Run `docker compose exec web python manage.py test`. The suite covers authentication, permissions, CSRF, private history, purchases and rollback on failure.

For a history-isolation demonstration, create a second customer and show that their purchase list is empty.

## JWT authentication

The API uses Simple JWT. The Jinja2 interface uses Django sessions. Both use the same username and password. Browser sign-out ends the browser session. API clients explicitly revoke refresh tokens.

| Method | Address | Body |
| --- | --- | --- |
| POST | /api/token/ | username and password |
| POST | /api/token/refresh/ | refresh |
| POST | /api/token/revoke/ | refresh |

Access tokens last five minutes. Refresh tokens last one day. Each successful refresh returns a new access token and a new refresh token. Save both and discard the previous pair. The previous refresh token is blacklisted.

Revocation blocks further refreshes with the revoked token. An already issued access token remains valid until its expiry, for at most five minutes. Password changes and account deactivation block both access and refresh usage.

Refresh requests run in an SQLite IMMEDIATE transaction to prevent simultaneous reuse of the same refresh token.

## JWT demonstration in Postman

1. Start the service with `docker compose up --build -d`. Open http://127.0.0.1:8000/login/ and sign in as an administrator. If needed, create one with `docker compose exec web python manage.py createsuperuser`.
2. In Users, create a new customer with a password and balance of 10000.00. In Fuel, create a new product with a price of 500.00 and stock of 1000.00 litres. Record its ID from the edit URL.
3. In Postman, create an environment with `base_url` set to `http://127.0.0.1:8000`. Keep token values local. Use Body → raw → JSON for POST requests.
4. POST `{{base_url}}/api/token/` with the customer's username and password. Use No Auth on token endpoints. Save the returned strings as local variables `access_token` and `refresh_token`.
5. GET `{{base_url}}/api/purchases/` with Authorization → Bearer Token → `{{access_token}}`. A new customer receives an empty list.
6. POST to the same URL with the same Bearer token and the body below, substituting the actual product ID.

```json
{"product_id": 1, "litres": "10.00"}
```

7. Expect HTTP 201, total_price 5000.00, remaining_balance 5000.00 and remaining_stock_litres 990.00. GET the history again to see the purchase.
8. POST `{{base_url}}/api/token/refresh/` with the body below. Save the previous refresh value temporarily for the reuse check, then replace both token variables with the new values.

```json
{"refresh": "{{refresh_token}}"}
```

9. Try refreshing with the previous token. Expect HTTP 401. GET the purchase history with the new access token. Expect HTTP 200.
10. POST `{{base_url}}/api/token/revoke/` with the current refresh token. Expect HTTP 200. Try refreshing with that token. Expect HTTP 401.
11. Clear cookies for this host in Postman, remove Authorization and GET the history. Expect HTTP 401. An invalid Bearer token also returns HTTP 401.
12. Obtain another customer token and POST /api/admin/products/ with it. Expect HTTP 403. A staff token permits management requests.
13. Run `docker compose exec web python manage.py test` to show the full test suite.

Use a new customer and product when repeating the demonstration so that the starting balance and stock match the expected results. After a restart, use `docker compose exec web python manage.py migrate --check` to verify that migrations are complete.
