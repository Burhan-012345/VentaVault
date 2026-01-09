"""
VantaVault - Animation Controller
Handles unlock animations and transitions
"""
import time
import secrets
import json
from datetime import datetime, timedelta

class AnimationController:
    def __init__(self):
        self.animation_tokens = {}
    
    def generate_token(self):
        """Generate animation token for unlock"""
        token = secrets.token_urlsafe(32)
        expiry = datetime.now() + timedelta(minutes=5)
        self.animation_tokens[token] = {
            'expiry': expiry,
            'used': False
        }
        return token
    
    def validate_token(self, token):
        """Validate animation token"""
        if token not in self.animation_tokens:
            return False
        
        token_data = self.animation_tokens[token]
        
        # Check expiry
        if datetime.now() > token_data['expiry']:
            del self.animation_tokens[token]
            return False
        
        # Check if already used
        if token_data['used']:
            return False
        
        # Mark as used
        token_data['used'] = True
        return True
    
    def get_unlock_animation_sequence(self):
        """Get unlock animation sequence"""
        return {
            'sequence': [
                {
                    'type': 'scan',
                    'duration': 1.5,
                    'properties': {
                        'color': '#00ff00',
                        'width': '80%',
                        'height': '2px'
                    }
                },
                {
                    'type': 'glow',
                    'duration': 1.0,
                    'properties': {
                        'color': 'rgba(0, 255, 0, 0.3)',
                        'spread': '50px'
                    }
                },
                {
                    'type': 'expand',
                    'duration': 0.8,
                    'properties': {
                        'scale': 1.2
                    }
                },
                {
                    'type': 'fade',
                    'duration': 0.5,
                    'properties': {
                        'opacity': 0
                    }
                }
            ],
            'total_duration': 3.8
        }
    
    def cleanup_expired_tokens(self):
        """Clean up expired animation tokens"""
        now = datetime.now()
        expired_tokens = [
            token for token, data in self.animation_tokens.items()
            if now > data['expiry']
        ]
        
        for token in expired_tokens:
            del self.animation_tokens[token]