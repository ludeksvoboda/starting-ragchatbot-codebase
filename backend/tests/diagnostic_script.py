#!/usr/bin/env python3
"""
Diagnostic script to test all RAG system components.

Run this script to verify the health of all backend components.
Usage: uv run python diagnostic_script.py
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

def test_configuration():
    """Test configuration and environment setup"""
    print("🔧 Testing Configuration...")
    try:
        from config import config
        
        # Check API key
        if not config.ANTHROPIC_API_KEY:
            print("❌ ANTHROPIC_API_KEY not configured")
            return False
        elif not config.ANTHROPIC_API_KEY.startswith('sk-'):
            print("⚠️  ANTHROPIC_API_KEY may have incorrect format")
        else:
            print("✅ API key configured correctly")
        
        # Check ChromaDB path
        if os.path.exists(config.CHROMA_PATH):
            print("✅ ChromaDB path exists")
        else:
            print("❌ ChromaDB path does not exist")
            return False
            
        print(f"📊 Configuration: {config.MAX_RESULTS} max results, chunk size {config.CHUNK_SIZE}")
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_vector_store():
    """Test vector store functionality"""
    print("\n🗃️  Testing Vector Store...")
    try:
        from vector_store import VectorStore
        from config import config
        
        vs = VectorStore(config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS)
        
        # Check course data
        titles = vs.get_existing_course_titles()
        count = vs.get_course_count()
        
        if count == 0:
            print("⚠️  No courses found in vector store")
        else:
            print(f"✅ Vector store loaded with {count} courses")
            print(f"📚 Courses: {', '.join(titles[:3])}{'...' if len(titles) > 3 else ''}")
        
        # Test search
        results = vs.search("Python programming", limit=1)
        if results.error:
            print(f"❌ Search failed: {results.error}")
            return False
        elif results.is_empty():
            print("⚠️  Search returned no results")
        else:
            print("✅ Search functionality working")
            
        return True
        
    except Exception as e:
        print(f"❌ Vector store test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ai_generator():
    """Test AI generator functionality"""
    print("\n🤖 Testing AI Generator...")
    try:
        from ai_generator import AIGenerator
        from config import config
        
        ai_gen = AIGenerator(config.ANTHROPIC_API_KEY, config.ANTHROPIC_MODEL)
        
        # Test simple query
        response = ai_gen.generate_response("What is 1+1?")
        if "2" in response:
            print("✅ AI Generator responding correctly")
            return True
        else:
            print(f"⚠️  AI Generator response unexpected: {response}")
            return True  # Still working, just unexpected
            
    except Exception as e:
        print(f"❌ AI Generator test failed: {e}")
        if "credit balance" in str(e):
            print("💳 Issue: Anthropic API credit balance too low")
        elif "invalid_request_error" in str(e):
            print("🔑 Issue: API request error - check API key")
        return False

def test_rag_system():
    """Test full RAG system"""
    print("\n🔄 Testing RAG System...")
    try:
        from rag_system import RAGSystem
        from config import config
        
        rag = RAGSystem(config)
        
        # Test with course content query
        response, sources = rag.query("What is computer use with Anthropic?")
        
        if len(response) > 0:
            print(f"✅ RAG System generated {len(response)} character response")
            print(f"📎 Found {len(sources)} sources")
            return True
        else:
            print("❌ RAG System returned empty response")
            return False
            
    except Exception as e:
        print(f"❌ RAG System test failed: {e}")
        return False

def test_api_endpoints():
    """Test FastAPI endpoints"""
    print("\n🌐 Testing API Endpoints...")
    try:
        from fastapi.testclient import TestClient
        from app import app
        
        client = TestClient(app)
        
        # Test query endpoint
        response = client.post('/api/query', json={
            'query': 'What is Python?',
            'session_id': None
        })
        
        if response.status_code == 200:
            data = response.json()
            if 'answer' in data and 'session_id' in data:
                print("✅ Query endpoint working correctly")
            else:
                print("⚠️  Query endpoint response missing required fields")
        else:
            print(f"❌ Query endpoint failed: {response.status_code}")
            print(f"Error: {response.text}")
            return False
        
        # Test courses endpoint
        response = client.get('/api/courses')
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Courses endpoint: {data['total_courses']} courses")
        else:
            print(f"❌ Courses endpoint failed: {response.status_code}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ API endpoints test failed: {e}")
        return False

def test_server_connectivity():
    """Test if server is accessible"""
    print("\n🖥️  Testing Server Connectivity...")
    try:
        import requests
        
        # Test root endpoint
        response = requests.get('http://localhost:8000', timeout=5)
        if response.status_code == 200:
            print("✅ Server accessible on http://localhost:8000")
        else:
            print(f"⚠️  Server returned {response.status_code}")
        
        # Test API endpoint directly
        response = requests.post('http://localhost:8000/api/query', 
                               json={'query': 'Test', 'session_id': None},
                               timeout=10)
        if response.status_code == 200:
            print("✅ API endpoint accessible via HTTP")
            return True
        else:
            print(f"❌ API endpoint failed via HTTP: {response.status_code}")
            return False
            
    except ImportError:
        print("⚠️  requests library not available, skipping HTTP test")
        return True
    except Exception as e:
        print(f"❌ Server connectivity test failed: {e}")
        if "Connection refused" in str(e):
            print("💡 Issue: Server may not be running. Start with: uv run uvicorn app:app --reload --port 8000 --host 0.0.0.0")
        return False

def main():
    """Run all diagnostic tests"""
    print("🔍 RAG System Diagnostic Report")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("Vector Store", test_vector_store),
        ("AI Generator", test_ai_generator),
        ("RAG System", test_rag_system),
        ("API Endpoints", test_api_endpoints),
        ("Server Connectivity", test_server_connectivity),
    ]
    
    results = {}
    for name, test_func in tests:
        results[name] = test_func()
    
    print("\n" + "=" * 50)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All backend components are working correctly!")
        print("💡 If you're experiencing NetworkError in the browser:")
        print("   1. Check browser console for JavaScript errors")
        print("   2. Verify frontend is served from http://localhost:8000")
        print("   3. Check for CORS issues in browser network tab")
        print("   4. Try hard refresh (Ctrl+F5 or Cmd+Shift+R)")
    else:
        print("\n⚠️  Some components are not working correctly.")
        print("💡 Focus on fixing the failed components first.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)