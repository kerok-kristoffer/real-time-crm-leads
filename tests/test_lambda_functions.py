"""
Simple validation tests for Lambda functions.
These tests validate the core logic without complex mocking.
"""
import json
import sys
import os

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'refinement'))


def test_refinement_lambda_cleans_data():
    """Test that refinement lambda correctly cleans lead data."""
    # Import the refinement lambda module
    refinement_path = os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'refinement')
    sys.path.insert(0, refinement_path)
    import lambda_function as refinement
    sys.path.remove(refinement_path)
    
    # Test data cleaning functions
    print("Testing clean_string...")
    assert refinement.clean_string('  John Doe  ') == 'John Doe'
    assert refinement.clean_string('') == ''
    print("  ✓ clean_string works")
    
    print("Testing clean_email...")
    assert refinement.clean_email('  JOHN@EXAMPLE.COM  ') == 'john@example.com'
    assert refinement.clean_email('invalid') == ''
    print("  ✓ clean_email works")
    
    print("Testing clean_phone...")
    result = refinement.clean_phone('+1 (555) 123-4567')
    assert len(result) > 0
    print("  ✓ clean_phone works")


def test_refinement_lambda_processes_raw_data():
    """Test that refinement lambda correctly processes raw data structure."""
    # Import the refinement lambda module
    refinement_path = os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'refinement')
    sys.path.insert(0, refinement_path)
    import lambda_function as refinement
    sys.path.remove(refinement_path)
    
    # Create test raw data
    raw_data = {
        'lead_id': 'test-123',
        'timestamp': '2024-01-15T10:30:00Z',
        'raw_data': {
            'name': '  John Doe  ',
            'email': 'JOHN@EXAMPLE.COM',
            'phone': '555-1234',
            'company': 'Test Corp',
            'source': 'Website',
            'owner': 'sales@example.com'
        },
        'status': 'captured'
    }
    
    print("Testing refine_lead_data...")
    # Process data
    refined = refinement.refine_lead_data(raw_data)
    
    # Verify structure
    assert refined['lead_id'] == 'test-123'
    assert refined['captured_at'] == '2024-01-15T10:30:00Z'
    assert 'processed_at' in refined
    assert refined['status'] == 'refined'
    
    # Verify contact data is cleaned
    assert refined['contact']['name'] == 'John Doe'
    assert refined['contact']['email'] == 'john@example.com'
    assert refined['contact']['phone'] == '555-1234'
    assert refined['contact']['company'] == 'Test Corp'
    
    # Verify lead details
    assert refined['lead_details']['source'] == 'Website'
    assert refined['lead_details']['owner'] == 'sales@example.com'
    print("  ✓ refine_lead_data works")


def test_json_payload_structure():
    """Test that we can parse expected JSON structures."""
    print("Testing JSON parsing...")
    
    # Test API Gateway format
    api_gateway_event = {
        'body': json.dumps({
            'name': 'John Doe',
            'email': 'john@example.com'
        })
    }
    
    if isinstance(api_gateway_event['body'], str):
        payload = json.loads(api_gateway_event['body'])
    else:
        payload = api_gateway_event['body']
    
    assert payload['name'] == 'John Doe'
    assert payload['email'] == 'john@example.com'
    
    # Test direct JSON format
    direct_event = {
        'name': 'Jane Smith',
        'email': 'jane@example.com'
    }
    
    assert direct_event['name'] == 'Jane Smith'
    print("  ✓ JSON parsing works")


if __name__ == '__main__':
    print("=" * 50)
    print("Running Lambda Function Validation Tests")
    print("=" * 50)
    print()
    
    all_passed = True
    
    try:
        test_refinement_lambda_cleans_data()
        print("✓ test_refinement_lambda_cleans_data PASSED")
    except Exception as e:
        print(f"✗ test_refinement_lambda_cleans_data FAILED: {e}")
        all_passed = False
    
    print()
    
    try:
        test_refinement_lambda_processes_raw_data()
        print("✓ test_refinement_lambda_processes_raw_data PASSED")
    except Exception as e:
        print(f"✗ test_refinement_lambda_processes_raw_data FAILED: {e}")
        all_passed = False
    
    print()
    
    try:
        test_json_payload_structure()
        print("✓ test_json_payload_structure PASSED")
    except Exception as e:
        print(f"✗ test_json_payload_structure FAILED: {e}")
        all_passed = False
    
    print()
    print("=" * 50)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 50)
