#!/usr/bin/env python3
"""
Schema Configuration System for Universal LTTng Kernel Trace Analysis

Provides modular schema selection and configuration management.
Allows switching between universal and specialized schemas by configuration.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

class SchemaType(Enum):
    """Available schema types"""
    UNIVERSAL = "universal"
    SPECIALIZED = "specialized"
    CUSTOM = "custom"

@dataclass
class SchemaConfig:
    """Schema configuration settings"""
    schema_type: SchemaType
    schema_file: str
    description: str
    node_count: int
    relationship_count: int
    optimized_for: str

class SchemaConfigManager:
    """Manages schema configurations and selection"""
    
    def __init__(self, config_file: str = "schema_config.json"):
        self.config_file = Path(config_file)
        self.schemas: Dict[str, SchemaConfig] = {}
        self._load_default_schemas()
        self._load_user_config()
    
    def _load_default_schemas(self):
        """Load default schema configurations"""
        # Get the project root (parent of src directory)
        project_root = Path(__file__).parent.parent
        schema_path = project_root / "schemas" / "kernel_trace_schema.cypher"
        
        self.schemas = {
            "universal_kernel": SchemaConfig(
                schema_type=SchemaType.UNIVERSAL,
                schema_file=str(schema_path),
                description="Universal LTTng kernel trace schema - works with any application",
                node_count=10,
                relationship_count=11,
                optimized_for="Cross-application compatibility, any LTTng traced binary"
            ),
            "performance_optimized": SchemaConfig(
                schema_type=SchemaType.SPECIALIZED,
                schema_file="performance_trace_schema.cypher",
                description="Performance-focused schema for high-throughput applications",
                node_count=8,
                relationship_count=9,
                optimized_for="High-performance applications, minimal graph overhead"
            ),
            "security_focused": SchemaConfig(
                schema_type=SchemaType.SPECIALIZED,
                schema_file="security_trace_schema.cypher",
                description="Security analysis schema with detailed permission tracking",
                node_count=12,
                relationship_count=15,
                optimized_for="Security analysis, permission tracking, audit trails"
            ),
            "network_intensive": SchemaConfig(
                schema_type=SchemaType.SPECIALIZED,
                schema_file="network_trace_schema.cypher", 
                description="Network-focused schema for distributed applications",
                node_count=11,
                relationship_count=13,
                optimized_for="Network applications, distributed systems, socket analysis"
            )
        }
    
    def _load_user_config(self):
        """Load user-defined schema configurations"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    user_configs = json.load(f)
                
                for name, config_data in user_configs.items():
                    self.schemas[name] = SchemaConfig(
                        schema_type=SchemaType(config_data["schema_type"]),
                        schema_file=config_data["schema_file"],
                        description=config_data["description"],
                        node_count=config_data["node_count"],
                        relationship_count=config_data["relationship_count"],
                        optimized_for=config_data["optimized_for"]
                    )
            except Exception as e:
                print(f"Warning: Could not load user schema config: {e}")
    
    def save_config(self):
        """Save current configurations to file"""
        config_data = {}
        for name, schema in self.schemas.items():
            if name not in ["universal_kernel", "performance_optimized", "security_focused", "network_intensive"]:
                # Only save user-added schemas
                config_data[name] = {
                    "schema_type": schema.schema_type.value,
                    "schema_file": schema.schema_file,
                    "description": schema.description,
                    "node_count": schema.node_count,
                    "relationship_count": schema.relationship_count,
                    "optimized_for": schema.optimized_for
                }
        
        if config_data:
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
    
    def add_schema(self, name: str, schema_config: SchemaConfig):
        """Add a new schema configuration"""
        self.schemas[name] = schema_config
        self.save_config()
    
    def get_schema(self, name: str) -> Optional[SchemaConfig]:
        """Get schema configuration by name"""
        return self.schemas.get(name)
    
    def list_schemas(self) -> Dict[str, SchemaConfig]:
        """List all available schemas"""
        return self.schemas.copy()
    
    def get_default_schema(self) -> SchemaConfig:
        """Get the default schema (universal kernel)"""
        return self.schemas["universal_kernel"]
    
    def validate_schema_file(self, schema_name: str) -> bool:
        """Validate that schema file exists"""
        schema = self.get_schema(schema_name)
        if not schema:
            return False
        
        schema_path = Path(schema.schema_file)
        return schema_path.exists()
    
    def get_active_schema_file(self, schema_name: str = "universal_kernel") -> str:
        """Get the active schema file path"""
        schema = self.get_schema(schema_name)
        if not schema:
            schema = self.get_default_schema()
        
        return schema.schema_file
    
    def print_schema_info(self, schema_name: str = None):
        """Print schema information"""
        if schema_name:
            schema = self.get_schema(schema_name)
            if schema:
                print(f" Schema: {schema_name}")
                print(f"   Type: {schema.schema_type.value}")
                print(f"   File: {schema.schema_file}")
                print(f"   Description: {schema.description}")
                print(f"   Nodes: {schema.node_count}, Relationships: {schema.relationship_count}")
                print(f"   Optimized for: {schema.optimized_for}")
                print(f"   Available: {'' if self.validate_schema_file(schema_name) else ''}")
            else:
                print(f" Schema '{schema_name}' not found")
        else:
            print(" Available Schemas:")
            for name, schema in self.schemas.items():
                available = "" if self.validate_schema_file(name) else ""
                print(f"   {available} {name}: {schema.description}")


def main():
    """Demonstrate schema configuration system"""
    print(" Schema Configuration System")
    print("=" * 50)
    
    manager = SchemaConfigManager()
    
    print("\n Available Schemas:")
    manager.print_schema_info()
    
    print(f"\n Default Schema: {manager.get_active_schema_file()}")
    
    print("\n Usage Examples:")
    print("   # Use universal schema (default)")
    print("   python3 universal_graph_builder.py")
    print("   ")
    print("   # Use performance-optimized schema") 
    print("   python3 universal_graph_builder.py --schema performance_optimized")
    print("   ")
    print("   # Use custom schema")
    print("   python3 universal_graph_builder.py --schema my_custom_schema")

if __name__ == "__main__":
    main()