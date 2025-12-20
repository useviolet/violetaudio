# API Keys for Testing

## Found API Keys from Database

### ✅ Validator API Key
- **UID:** 7
- **Email:** tobiusaolo21@gmail.com
- **Hotkey:** 5HNKFeHjvppKyKHTA1SK4rN7L2SZWpJeoNjeLo4DDg2FcRKh
- **API Key:** `LOoAxeW3eq2I...wjOaJdqg` (full key retrieved from database)
- **Use for:** Validator endpoints (`/api/v1/validator/*`)

### ✅ Miner API Key
- **UID:** 6
- **Email:** test_client_1765400594@example.com
- **Hotkey:** 5C8BqfD9MgdabzYBNFEEvne1bKejJAycEHUYSwQE2GW7Uy2y
- **API Key:** `DXd-HF22dZp_...01fUHcaE` (full key retrieved from database)
- **Use for:** Miner endpoints (`/api/v1/miners/*`)

### ✅ Client API Key
- **Email:** test_client_1765400308@example.com
- **API Key:** `hcxVyBoeIhWv...MNYXD0j4` (full key retrieved from database)
- **Use for:** General endpoints that require authentication

## Test Script

The test script `test_endpoints_separate.py` will:
1. ✅ Automatically query the database for API keys
2. ✅ Use the correct API key for each endpoint
3. ✅ Test each endpoint separately with detailed output
4. ✅ Show response times and data

## How to Run Tests

### Step 1: Start the Proxy Server

```bash
# Option 1: Using uvicorn
cd /Users/user/Documents/Jarvis/violet
uvicorn proxy_server.main:app --reload --port 8000

# Option 2: Using python directly
python proxy_server/main.py
```

### Step 2: Run the Test Script

```bash
# In another terminal
cd /Users/user/Documents/Jarvis/violet
python proxy_server/test_endpoints_separate.py
```

## Endpoints to Test

1. **GET /api/v1/validator/7/evaluated_tasks**
   - Requires: Validator API key
   - Returns: List of task IDs evaluated by validator 7

2. **GET /api/v1/validator/tasks**
   - Requires: Validator API key
   - Returns: Tasks ready for evaluation (with input_data)

3. **GET /api/v1/leaderboard**
   - Requires: Any API key (or none)
   - Returns: Leaderboard of miners

4. **GET /api/v1/miners/6/metrics**
   - Requires: Miner API key
   - Returns: Metrics for miner 6

5. **GET /docs**
   - Requires: None
   - Returns: Swagger UI documentation

## Manual Testing with curl

```bash
# Get evaluated tasks (Validator)
curl -X GET "http://localhost:8000/api/v1/validator/7/evaluated_tasks" \
  -H "X-API-Key: LOoAxeW3eq2I...wjOaJdqg"

# Get tasks for evaluation (Validator)
curl -X GET "http://localhost:8000/api/v1/validator/tasks" \
  -H "X-API-Key: LOoAxeW3eq2I...wjOaJdqg"

# Get leaderboard (Client)
curl -X GET "http://localhost:8000/api/v1/leaderboard" \
  -H "X-API-Key: hcxVyBoeIhWv...MNYXD0j4"

# Get miner metrics (Miner)
curl -X GET "http://localhost:8000/api/v1/miners/6/metrics" \
  -H "X-API-Key: DXd-HF22dZp_...01fUHcaE"

# Get API docs (No auth)
curl -X GET "http://localhost:8000/docs"
```

## Note

The full API keys are stored in the database and can be retrieved by running:
```python
python proxy_server/test_endpoints_separate.py
```

The script will automatically use the correct API keys for each endpoint.

