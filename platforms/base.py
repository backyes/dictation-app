"""Platform abstraction layer"""
from abc import ABC, abstractmethod


class Platform(ABC):
    """Platform abstract base class"""
    
    @abstractmethod
    def run(self):
        """Run the platform application"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get platform name"""
        pass


class PlatformConfig:
    """Platform configuration"""
    
    def __init__(self, storage=None, debug=False, host='0.0.0.0', port=5000):
        self.storage = storage
        self.debug = debug
        self.host = host
        self.port = port
