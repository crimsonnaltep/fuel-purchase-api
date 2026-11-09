# Fuel Purchase API

Python 3.10 or newer, Django REST Framework, SQLite.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py create_admin operator
python manage.py runserver
```

Save the API key printed by `create_admin`. Send it in `X-Admin-Key` when managing users or products. In Postman, select **Body → raw → JSON** for POST and PATCH requests.

| Method | Path | Header |
| --- | --- | --- |
| POST | `/api/admin/products/` | `X-Admin-Key` |
| PATCH | `/api/admin/products/{product_id}/` | `X-Admin-Key` |
| POST | `/api/admin/users/` | `X-Admin-Key` |
| PATCH | `/api/admin/users/{user_id}/` | `X-Admin-Key` |
| POST | `/api/purchases/` | `X-Username` |
| GET | `/api/purchases/` | `X-Username` |

1. Create a product with `{"name":"Petrol 95","price_per_litre":"500.00","available_litres":"1000.00"}`.
2. Create a user with `{"username":"john","first_name":"John","last_name":"Smith","birthdate":"1995-05-20","account_balance":"10000.00"}`.
3. Send `{"product_id":1,"litres":"10.00"}` to `POST /api/purchases/` with `X-Username: john`. Use the product ID returned in step 1.
4. Send `GET /api/purchases/` with the same username to see the purchase history.

PATCH requests accept only the fields you want to change. Prices, balances, and litres use two decimal places. The purchase total rounds to the nearest cent, with half cents rounded up. User requests use the assignment's basic username header, so anyone who knows a username can act as that user.

## Tests

```bash
python manage.py test
```

## Docker

```bash
docker compose up --build -d
docker compose exec api python manage.py create_admin operator
docker compose exec api python manage.py test
```

The API is available at `http://127.0.0.1:8000`. Create the administrator once and save the printed key. The `fuel-data` volume preserves the SQLite database across container restarts and `docker compose down`. The container runs Django's local development server.
