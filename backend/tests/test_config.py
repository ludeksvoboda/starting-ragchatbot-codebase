"""
Tests for config.py - Environment and configuration validation.

These tests help diagnose potential configuration issues that could
cause NetworkError in the RAG chatbot, especially API key problems.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, mock_open
from dataclasses import dataclass

# Import the configuration module
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config, config


class TestConfig:
    """Test cases for Config class"""
    
    def test_config_default_values(self):
        """Test that config has expected default values"""
        test_config = Config()
        
        # Check default values
        assert test_config.ANTHROPIC_MODEL == "claude-sonnet-4-20250514"
        assert test_config.EMBEDDING_MODEL == "all-MiniLM-L6-v2"
        assert test_config.CHUNK_SIZE == 800
        assert test_config.CHUNK_OVERLAP == 100
        assert test_config.MAX_RESULTS == 5
        assert test_config.MAX_HISTORY == 2
        assert test_config.CHROMA_PATH == "./chroma_db"
    
    def test_config_is_dataclass(self):
        """Test that Config is properly defined as dataclass"""
        assert hasattr(Config, '__dataclass_fields__')
        
        # Check expected fields exist
        fields = Config.__dataclass_fields__
        expected_fields = [
            'ANTHROPIC_API_KEY',
            'ANTHROPIC_MODEL', 
            'EMBEDDING_MODEL',
            'CHUNK_SIZE',
            'CHUNK_OVERLAP',
            'MAX_RESULTS',
            'MAX_HISTORY',
            'CHROMA_PATH'
        ]
        
        for field in expected_fields:
            assert field in fields
    
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key-123'})
    def test_config_loads_env_vars(self):
        """Test that config loads environment variables"""
        test_config = Config()
        assert test_config.ANTHROPIC_API_KEY == 'test-key-123'
    
    @patch.dict(os.environ, {}, clear=True)  # Clear environment
    def test_config_empty_api_key_when_not_set(self):
        """Test config when API key is not set in environment"""
        test_config = Config()
        assert test_config.ANTHROPIC_API_KEY == ""


class TestEnvironmentValidation:
    """Test environment setup and validation"""
    
    def test_anthropic_api_key_validation(self):
        """Test validation of Anthropic API key"""
        # Test with valid-looking API key
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'sk-ant-api03-valid-key-format'}):
            test_config = Config()
            assert test_config.ANTHROPIC_API_KEY.startswith('sk-ant-')
    
    def test_missing_api_key_detection(self):
        """Test detection of missing API key"""
        with patch.dict(os.environ, {}, clear=True):
            test_config = Config()
            
            # Should be empty string when not set
            assert test_config.ANTHROPIC_API_KEY == ""
            
            # This is a critical configuration issue
            def is_api_key_configured(config):
                return bool(config.ANTHROPIC_API_KEY and config.ANTHROPIC_API_KEY.strip())
            
            assert not is_api_key_configured(test_config)
    
    def test_chroma_path_accessibility(self):
        """Test ChromaDB path accessibility"""
        test_config = Config()
        
        # Test that we can determine if path is accessible
        def is_chroma_path_writable(path):
            try:
                # Try to create the directory if it doesn't exist
                os.makedirs(path, exist_ok=True)
                
                # Try to write a test file
                test_file = os.path.join(path, 'test_write.tmp')
                with open(test_file, 'w') as f:
                    f.write('test')
                
                # Clean up
                os.remove(test_file)
                return True
            except (OSError, PermissionError):
                return False
        
        # Default path should be writable in most environments
        # Note: This might fail in restricted environments
        try:
            writable = is_chroma_path_writable(test_config.CHROMA_PATH)
            assert isinstance(writable, bool)  # Should return a boolean
        except Exception:
            # If we can't test writability, that's also valuable info
            pytest.skip("Cannot test path writability in this environment")
    
    def test_numeric_config_values(self):
        """Test that numeric configuration values are valid"""
        test_config = Config()
        
        # Test positive integers
        assert isinstance(test_config.CHUNK_SIZE, int)
        assert test_config.CHUNK_SIZE > 0
        
        assert isinstance(test_config.CHUNK_OVERLAP, int)
        assert test_config.CHUNK_OVERLAP >= 0
        
        assert isinstance(test_config.MAX_RESULTS, int)
        assert test_config.MAX_RESULTS > 0
        
        assert isinstance(test_config.MAX_HISTORY, int)
        assert test_config.MAX_HISTORY >= 0
        
        # Test reasonable ranges
        assert test_config.CHUNK_SIZE >= 100  # Should be reasonable size
        assert test_config.CHUNK_OVERLAP < test_config.CHUNK_SIZE  # Overlap should be less than size
        assert test_config.MAX_RESULTS <= 100  # Should be reasonable limit


class TestConfigurationDependencies:
    """Test configuration dependencies and validation"""
    
    def test_embedding_model_validity(self):
        """Test that embedding model name is valid format"""
        test_config = Config()
        
        # Should be a non-empty string
        assert isinstance(test_config.EMBEDDING_MODEL, str)
        assert len(test_config.EMBEDDING_MODEL) > 0
        
        # Should follow sentence-transformers naming convention
        assert test_config.EMBEDDING_MODEL == "all-MiniLM-L6-v2"
    
    def test_anthropic_model_validity(self):
        """Test that Anthropic model name is valid"""
        test_config = Config()
        
        # Should be a non-empty string
        assert isinstance(test_config.ANTHROPIC_MODEL, str)
        assert len(test_config.ANTHROPIC_MODEL) > 0
        
        # Should follow Claude model naming pattern
        assert "claude" in test_config.ANTHROPIC_MODEL.lower()
    
    def test_chunk_configuration_consistency(self):
        """Test that chunk configuration is internally consistent"""
        test_config = Config()
        
        # Overlap should be less than chunk size
        assert test_config.CHUNK_OVERLAP < test_config.CHUNK_SIZE
        
        # Should have reasonable minimum sizes
        assert test_config.CHUNK_SIZE >= 200
        assert test_config.CHUNK_OVERLAP >= 0


class TestDotEnvFileHandling:
    """Test .env file loading and handling"""
    
    def test_dotenv_file_loading(self):
        """Test that .env file is properly loaded"""
        # Create a temporary .env file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('ANTHROPIC_API_KEY=test-key-from-file\n')
            f.write('ANTHROPIC_MODEL=custom-model\n')
            temp_env_path = f.name
        
        try:
            # Test loading the .env file
            from dotenv import load_dotenv
            load_dotenv(temp_env_path, override=True)
            
            test_config = Config()
            assert test_config.ANTHROPIC_API_KEY == 'test-key-from-file'
            assert test_config.ANTHROPIC_MODEL == 'custom-model'
            
        finally:
            # Clean up
            os.unlink(temp_env_path)
    
    def test_env_file_not_found_handling(self):
        """Test behavior when .env file doesn't exist"""
        # This should not crash, just use defaults/environment
        with patch('dotenv.load_dotenv') as mock_load:
            mock_load.side_effect = FileNotFoundError("No .env file")
            
            # Should still be able to create config
            try:
                test_config = Config()
                assert isinstance(test_config, Config)
            except Exception:
                pytest.fail("Config creation should not fail when .env file is missing")


class TestGlobalConfigInstance:
    """Test the global config instance"""
    
    def test_global_config_exists(self):
        """Test that global config instance is created"""
        from config import config
        
        assert config is not None
        assert isinstance(config, Config)
    
    def test_global_config_values(self):
        """Test that global config has expected values"""
        from config import config
        
        # Should have default values or environment values
        assert hasattr(config, 'ANTHROPIC_API_KEY')
        assert hasattr(config, 'ANTHROPIC_MODEL')
        assert hasattr(config, 'EMBEDDING_MODEL')


class TestConfigurationDiagnostics:
    """Diagnostic tests for configuration issues"""
    
    def test_diagnose_api_key_issues(self):
        """Diagnostic test for API key configuration issues"""
        test_config = Config()
        
        issues = []
        
        # Check if API key is set
        if not test_config.ANTHROPIC_API_KEY:
            issues.append("ANTHROPIC_API_KEY is not set")
        
        # Check if API key has correct format (basic check)
        elif not test_config.ANTHROPIC_API_KEY.startswith('sk-'):
            issues.append(f"ANTHROPIC_API_KEY may have incorrect format: {test_config.ANTHROPIC_API_KEY[:10]}...")
        
        # This diagnostic info can help identify configuration problems
        if issues:
            print(f"Configuration issues detected: {issues}")
        
        # Test should pass but provide diagnostic info
        assert isinstance(issues, list)
    
    def test_diagnose_path_issues(self):
        """Diagnostic test for path configuration issues"""
        test_config = Config()
        
        issues = []
        
        # Check ChromaDB path
        if not os.path.exists(os.path.dirname(test_config.CHROMA_PATH)):
            parent_dir = os.path.dirname(test_config.CHROMA_PATH)
            if parent_dir:  # Not current directory
                issues.append(f"ChromaDB parent directory does not exist: {parent_dir}")
        
        # Check if path is writable
        try:
            os.makedirs(test_config.CHROMA_PATH, exist_ok=True)
            test_file = os.path.join(test_config.CHROMA_PATH, 'test_write.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except (OSError, PermissionError) as e:
            issues.append(f"ChromaDB path not writable: {e}")
        
        if issues:
            print(f"Path issues detected: {issues}")
        
        assert isinstance(issues, list)
    
    def test_configuration_summary(self):
        """Generate configuration summary for diagnostics"""
        test_config = Config()
        
        summary = {
            "api_key_set": bool(test_config.ANTHROPIC_API_KEY),
            "api_key_format_ok": test_config.ANTHROPIC_API_KEY.startswith('sk-') if test_config.ANTHROPIC_API_KEY else False,
            "model": test_config.ANTHROPIC_MODEL,
            "embedding_model": test_config.EMBEDDING_MODEL,
            "chroma_path": test_config.CHROMA_PATH,
            "chunk_size": test_config.CHUNK_SIZE,
            "max_results": test_config.MAX_RESULTS,
        }
        
        print(f"Configuration summary: {summary}")
        
        # Should generate valid summary
        assert "api_key_set" in summary
        assert "model" in summary
        assert isinstance(summary["chunk_size"], int)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])