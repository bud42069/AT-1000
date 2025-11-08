"""
Comprehensive Backend API Testing for Solana Auto-Trader
Tests all endpoints: SIWS auth, engine, settings
"""
import requests
import sys
import json
from datetime import datetime

class BackendAPITester:
    def __init__(self, base_url="https://solana-autotrader-3.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        
    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)
        
        self.tests_run += 1
        print(f"\n{'='*60}")
        print(f"🔍 Test {self.tests_run}: {name}")
        print(f"   Method: {method} {endpoint}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            
            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED - Status: {response.status_code}")
                try:
                    resp_json = response.json()
                    print(f"   Response: {json.dumps(resp_json, indent=2)[:200]}...")
                except:
                    print(f"   Response: {response.text[:200]}")
            else:
                print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:300]}")
                self.failed_tests.append({
                    "test": name,
                    "endpoint": endpoint,
                    "expected": expected_status,
                    "actual": response.status_code,
                    "response": response.text[:200]
                })
            
            return success, response.json() if response.text else {}
            
        except requests.exceptions.Timeout:
            print(f"❌ FAILED - Request timeout after 10s")
            self.failed_tests.append({
                "test": name,
                "endpoint": endpoint,
                "error": "Timeout"
            })
            return False, {}
        except Exception as e:
            print(f"❌ FAILED - Error: {str(e)}")
            self.failed_tests.append({
                "test": name,
                "endpoint": endpoint,
                "error": str(e)
            })
            return False, {}
    
    def test_root(self):
        """Test root endpoint"""
        return self.run_test(
            "Root Endpoint",
            "GET",
            "/api/",
            200
        )
    
    def test_version(self):
        """Test version endpoint"""
        return self.run_test(
            "Version Endpoint",
            "GET",
            "/api/version",
            200
        )
    
    def test_engine_ping(self):
        """Test engine ping endpoint"""
        return self.run_test(
            "Engine Ping",
            "GET",
            "/api/engine/ping",
            200
        )
    
    def test_engine_guards(self):
        """Test engine guards endpoint"""
        success, response = self.run_test(
            "Engine Guards",
            "GET",
            "/api/engine/guards",
            200
        )
        
        if success:
            # Validate guard fields
            required_fields = ['spread_bps', 'depth_ok', 'liq_gap_atr_ok', 'funding_apr', 'basis_bps', 'timestamp']
            missing = [f for f in required_fields if f not in response]
            if missing:
                print(f"⚠️  WARNING: Missing guard fields: {missing}")
        
        return success, response
    
    def test_engine_activity(self):
        """Test engine activity log endpoint"""
        return self.run_test(
            "Engine Activity Log",
            "GET",
            "/api/engine/activity",
            200
        )
    
    def test_place_order(self):
        """Test placing an order"""
        order_intent = {
            "side": "long",
            "type": "post_only_limit",
            "px": 150.50,
            "size": 1.0,
            "sl": 145.00,
            "tp1": 155.00,
            "tp2": 160.00,
            "tp3": 165.00,
            "leverage": 5,
            "venue": "drift",
            "notes": "Test order from backend_test.py"
        }
        
        success, response = self.run_test(
            "Place Order",
            "POST",
            "/api/engine/orders",
            200,
            data=order_intent
        )
        
        if success and 'orderId' in response:
            return success, response['orderId']
        
        return success, None
    
    def test_cancel_order(self, order_id):
        """Test cancelling an order"""
        if not order_id:
            print("⚠️  Skipping cancel test - no order_id available")
            return False, {}
        
        return self.run_test(
            "Cancel Order",
            "POST",
            "/api/engine/cancel",
            200,
            data={"orderId": order_id}
        )
    
    def test_kill_switch(self):
        """Test emergency kill switch"""
        return self.run_test(
            "Kill Switch",
            "POST",
            "/api/engine/kill",
            200,
            data={"reason": "Test kill switch from backend_test.py"}
        )
    
    def test_siws_challenge(self):
        """Test SIWS challenge generation"""
        success, response = self.run_test(
            "SIWS Challenge",
            "GET",
            "/api/auth/siws/challenge",
            200
        )
        
        if success:
            required_fields = ['message', 'nonce', 'exp']
            missing = [f for f in required_fields if f not in response]
            if missing:
                print(f"⚠️  WARNING: Missing challenge fields: {missing}")
            else:
                print(f"   Challenge nonce: {response.get('nonce', 'N/A')}")
        
        return success, response
    
    def test_settings_get(self):
        """Test getting user settings"""
        return self.run_test(
            "Get Settings",
            "GET",
            "/api/settings?user_id=test_user_123",
            200
        )
    
    def test_settings_update(self):
        """Test updating user settings"""
        settings = {
            "userId": "test_user_123",
            "max_leverage": 8,
            "risk_per_trade": 0.5,
            "daily_drawdown_limit": 1.5,
            "priority_fee_cap": 2000,
            "delegate_enabled": True,
            "strategy_enabled": False
        }
        
        return self.run_test(
            "Update Settings",
            "PUT",
            "/api/settings",
            200,
            data=settings
        )
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*60}")
        print(f"📊 TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed} ✅")
        print(f"Failed: {len(self.failed_tests)} ❌")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            print(f"\n{'='*60}")
            print(f"❌ FAILED TESTS DETAILS:")
            print(f"{'='*60}")
            for i, failure in enumerate(self.failed_tests, 1):
                print(f"\n{i}. {failure.get('test', 'Unknown')}")
                print(f"   Endpoint: {failure.get('endpoint', 'N/A')}")
                if 'expected' in failure:
                    print(f"   Expected: {failure['expected']}, Got: {failure['actual']}")
                if 'error' in failure:
                    print(f"   Error: {failure['error']}")
                if 'response' in failure:
                    print(f"   Response: {failure['response']}")

def main():
    print("="*60)
    print("🚀 Starting Backend API Tests")
    print("="*60)
    print(f"Target: https://solana-autotrader-3.preview.emergentagent.com")
    print(f"Time: {datetime.now().isoformat()}")
    
    tester = BackendAPITester()
    
    # Test basic endpoints
    print("\n\n🔹 TESTING BASIC ENDPOINTS")
    tester.test_root()
    tester.test_version()
    
    # Test engine endpoints
    print("\n\n🔹 TESTING ENGINE ENDPOINTS")
    tester.test_engine_ping()
    tester.test_engine_guards()
    tester.test_engine_activity()
    
    # Test order flow
    print("\n\n🔹 TESTING ORDER FLOW")
    success, order_id = tester.test_place_order()
    if success and order_id:
        tester.test_cancel_order(order_id)
    
    # Test kill switch
    tester.test_kill_switch()
    
    # Test SIWS auth
    print("\n\n🔹 TESTING SIWS AUTHENTICATION")
    tester.test_siws_challenge()
    # Note: Cannot test full SIWS verify without wallet signature
    
    # Test settings
    print("\n\n🔹 TESTING SETTINGS ENDPOINTS")
    tester.test_settings_get()
    tester.test_settings_update()
    
    # Print summary
    tester.print_summary()
    
    # Return exit code
    return 0 if len(tester.failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
