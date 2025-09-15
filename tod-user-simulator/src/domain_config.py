"""
Domain Configuration Manager for TOD User Simulator

This module provides domain-specific configurations for hotel, restaurant, 
and flight booking domains used in the Task-Oriented Dialogue system.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import json


@dataclass
class DomainConfig:
    """Data class representing a domain configuration."""
    name: str
    description: str
    intent_list: Dict[str, str]
    slots_to_fill: Dict[str, List[str]]
    action_slot_pair: Dict[str, List[str]]
    
    def to_dict(self) -> Dict:
        """Convert domain configuration to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DomainConfig':
        """Create domain configuration from dictionary."""
        return cls(**data)
    
    def validate(self) -> List[str]:
        """Validate domain configuration and return list of errors."""
        errors = []
        
        if not self.name or not isinstance(self.name, str):
            errors.append("Domain name must be a non-empty string")
        
        if not self.description or not isinstance(self.description, str):
            errors.append("Domain description must be a non-empty string")
        
        if not isinstance(self.intent_list, dict) or not self.intent_list:
            errors.append("Intent list must be a non-empty dictionary")
        
        if not isinstance(self.slots_to_fill, dict):
            errors.append("Slots to fill must be a dictionary")
        
        if not isinstance(self.action_slot_pair, dict):
            errors.append("Action slot pair must be a dictionary")
        
        # Validate that slots referenced in action_slot_pair exist in slots_to_fill
        if isinstance(self.action_slot_pair, dict):
            for action, slots in self.action_slot_pair.items():
                if not isinstance(slots, list):
                    errors.append(f"Action '{action}' must have a list of slots")
                    continue
                for slot in slots:
                    if isinstance(self.slots_to_fill, dict) and slot not in self.slots_to_fill:
                        errors.append(f"Slot '{slot}' in action '{action}' not found in slots_to_fill")
        
        # Validate that intents referenced in slots_to_fill exist in intent_list
        if isinstance(self.slots_to_fill, dict):
            for slot, intents in self.slots_to_fill.items():
                if not isinstance(intents, list):
                    errors.append(f"Slot '{slot}' must have a list of intents")
                    continue
                for intent in intents:
                    if isinstance(self.intent_list, dict) and intent not in self.intent_list:
                        errors.append(f"Intent '{intent}' for slot '{slot}' not found in intent_list")
        
        return errors


class DomainConfigManager:
    """Manager class for handling domain configurations."""
    
    def __init__(self):
        """Initialize the domain configuration manager with predefined domains."""
        self._domains = self._initialize_domains()
    
    def _initialize_domains(self) -> Dict[str, DomainConfig]:
        """Initialize predefined domain configurations."""
        domains = {}
        
        # Hotel domain configuration
        hotel_config = DomainConfig(
            name="hotel",
            description="You are a helpful hotel assistant, your job is to help users in whatever queries they may have.",
            intent_list={
                "book_room": "The user wants to book a room in the hotel",
                "cancel_booking": "The user wants to cancel an existing booking",
                "general_enquiries": "The user wants to ask general questions about the hotel",
                "chit_chat": "Queries outside of the other intents specified. Apart from greetings and hellos, the response for this one should be 'Sorry, I can only help you with hotel queries.'"
            },
            slots_to_fill={
                "dateFrom": ["book_room"],
                "dateTo": ["book_room"],
                "bookingID": ["cancel_booking"]
            },
            action_slot_pair={
                "makeBooking": ["dateFrom", "dateTo"],
                "lookUpBooking": ["bookingID"],
                "cancellation": ["bookingID"]
            }
        )
        domains["hotel"] = hotel_config
        
        # Restaurant domain configuration
        restaurant_config = DomainConfig(
            name="restaurant",
            description="You are a helpful restaurant assistant, your job is to help users with reservations and inquiries.",
            intent_list={
                "make_reservation": "The user wants to make a restaurant reservation",
                "cancel_reservation": "The user wants to cancel an existing reservation",
                "menu_inquiry": "The user wants to ask about menu items or dietary options",
                "chit_chat": "Queries outside of the other intents specified. Apart from greetings and hellos, the response for this one should be 'Sorry, I can only help you with restaurant queries.'"
            },
            slots_to_fill={
                "date": ["make_reservation"],
                "time": ["make_reservation"],
                "party_size": ["make_reservation"],
                "reservationID": ["cancel_reservation"]
            },
            action_slot_pair={
                "makeReservation": ["date", "time", "party_size"],
                "cancelReservation": ["reservationID"],
                "checkAvailability": ["date", "time"]
            }
        )
        domains["restaurant"] = restaurant_config
        
        # Flight domain configuration
        flight_config = DomainConfig(
            name="flight",
            description="You are a helpful flight booking assistant, your job is to help users with flight bookings and travel inquiries.",
            intent_list={
                "book_flight": "The user wants to book a flight",
                "cancel_booking": "The user wants to cancel an existing flight booking",
                "flight_status": "The user wants to check flight status or information",
                "chit_chat": "Queries outside of the other intents specified. Apart from greetings and hellos, the response for this one should be 'Sorry, I can only help you with flight queries.'"
            },
            slots_to_fill={
                "departure_city": ["book_flight"],
                "arrival_city": ["book_flight"],
                "departure_date": ["book_flight"],
                "return_date": ["book_flight"],
                "bookingID": ["cancel_booking", "flight_status"]
            },
            action_slot_pair={
                "searchFlights": ["departure_city", "arrival_city", "departure_date"],
                "bookFlight": ["departure_city", "arrival_city", "departure_date"],
                "cancelBooking": ["bookingID"],
                "checkStatus": ["bookingID"]
            }
        )
        domains["flight"] = flight_config
        
        return domains
    
    def get_domain_config(self, domain: str) -> Optional[DomainConfig]:
        """
        Get domain configuration by name.
        
        Args:
            domain: Name of the domain (hotel, restaurant, flight)
            
        Returns:
            DomainConfig object if found, None otherwise
        """
        return self._domains.get(domain.lower())
    
    def list_available_domains(self) -> List[str]:
        """
        Get list of available domain names.
        
        Returns:
            List of available domain names
        """
        return list(self._domains.keys())
    
    def validate_domain_config(self, domain: str) -> List[str]:
        """
        Validate a domain configuration.
        
        Args:
            domain: Name of the domain to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        config = self.get_domain_config(domain)
        if not config:
            return [f"Domain '{domain}' not found"]
        
        return config.validate()
    
    def add_domain_config(self, config: DomainConfig) -> bool:
        """
        Add a new domain configuration.
        
        Args:
            config: DomainConfig object to add
            
        Returns:
            True if added successfully, False if validation fails
        """
        errors = config.validate()
        if errors:
            return False
        
        self._domains[config.name.lower()] = config
        return True
    
    def export_domain_config(self, domain: str) -> Optional[str]:
        """
        Export domain configuration as JSON string.
        
        Args:
            domain: Name of the domain to export
            
        Returns:
            JSON string representation of the domain config, None if not found
        """
        config = self.get_domain_config(domain)
        if not config:
            return None
        
        return json.dumps(config.to_dict(), indent=2)
    
    def import_domain_config(self, json_str: str) -> bool:
        """
        Import domain configuration from JSON string.
        
        Args:
            json_str: JSON string representation of domain config
            
        Returns:
            True if imported successfully, False otherwise
        """
        try:
            data = json.loads(json_str)
            config = DomainConfig.from_dict(data)
            return self.add_domain_config(config)
        except (json.JSONDecodeError, TypeError, ValueError):
            return False