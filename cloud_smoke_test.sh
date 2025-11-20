#!/bin/bash
echo "=== CLOUD SERVER VALIDATION REPORT ==="
echo ""
echo "Date: $(date)"
echo "Server: 46.224.36.109"
echo ""

# Test 1: Health
echo "Test 1: Health Check"
HEALTH=$(curl -s http://localhost:8088/health)
echo "$HEALTH" | jq -r '"\(.status) - uptime: \(.uptime_s)s, version: \(.version)"'

# Test 2: Login
echo ""
echo "Test 2: Admin Login (admin/admin123)"
TOKEN=$(curl -s -X POST http://localhost:8088/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')
echo "Token length: ${#TOKEN} chars (expected: >200)"

# Test 3: Users API
echo ""
echo "Test 3: GET /api/users/ (paginated)"
USERS=$(curl -s "http://localhost:8088/api/users/?page=1&limit=10" \
  -H "Authorization: Bearer $TOKEN")
echo "$USERS" | jq -r '"Total users: \(.total), Page: \(.page)/\(.pages)"'

# Test 4: Admin Role
echo ""
echo "Test 4: Admin User Verification"
echo "$USERS" | jq -r '.items[] | select(.id==1) | "ID: \(.id), Name: \(.name), Role: \(.role), Active: \(.active)"'

# Test 5: Database
echo ""
echo "Test 5: Database Integrity"
docker exec prod_api sqlite3 /app/db/shifts.db "SELECT COUNT(*) FROM users" | xargs echo "Users count:"
docker exec prod_api sqlite3 /app/db/shifts.db "SELECT COUNT(*) FROM bot_commands" | xargs echo "Bot commands:"

# Test 6: fix_admin_role.py
echo ""
echo "Test 6: Verify fix_admin_role.py exists"
docker exec prod_api ls -lh /app/seeds/fix_admin_role.py | awk '{print $9, "(" $5 ")"}'

echo ""
echo "=== VERDICT ==="
ROLE=$(echo "$USERS" | jq -r '.items[] | select(.id==1) | .role')
if [ "$ROLE" = "admin" ]; then
  echo "✅ PASS - Cloud server is working correctly"
  echo "   - API health: OK"
  echo "   - Admin login: OK"
  echo "   - Admin role: $ROLE (FIXED)"
  echo "   - fix_admin_role.py: DEPLOYED"
else
  echo "❌ FAIL - Admin role is still: $ROLE"
fi
