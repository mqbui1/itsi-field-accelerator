"""
Pre-built vertical service tree definitions for demo/workshop bootstrapping.

Each vertical returns a list of CI dicts compatible with CMDBParser.build_content_pack().
Use these when no customer CMDB data is available (demos, PoVs, workshops).
"""

from __future__ import annotations

VERTICALS: dict[str, list[dict]] = {

    "banking": [
        # Business services
        {"name": "Retail Banking Platform", "ci_class": "cmdb_ci_service", "parent": "", "business_service": "Retail Banking Platform", "description": "Top-level retail banking platform"},

        # Digital channels
        {"name": "Online Banking Portal", "ci_class": "web_server", "parent": "Retail Banking Platform", "business_service": "Retail Banking Platform", "description": "Customer-facing web banking"},
        {"name": "Mobile Banking API", "ci_class": "api_gateway", "parent": "Retail Banking Platform", "business_service": "Retail Banking Platform", "description": "Mobile app backend API"},

        # Core services
        {"name": "Account Service", "ci_class": "app_server", "parent": "Retail Banking Platform", "business_service": "Retail Banking Platform", "description": "Account management microservice"},
        {"name": "Payment Processing", "ci_class": "payment_processor", "parent": "Retail Banking Platform", "business_service": "Retail Banking Platform", "description": "Real-time payment processing"},
        {"name": "Fraud Detection Engine", "ci_class": "fraud_detection", "parent": "Retail Banking Platform", "business_service": "Retail Banking Platform", "description": "ML-based fraud scoring"},
        {"name": "Identity & Auth Service", "ci_class": "auth_service", "parent": "Retail Banking Platform", "business_service": "Retail Banking Platform", "description": "OAuth2/OIDC authentication"},

        # Data layer
        {"name": "Core Banking DB", "ci_class": "database", "parent": "Account Service", "business_service": "Retail Banking Platform", "description": "Primary PostgreSQL cluster"},
        {"name": "Transaction DB", "ci_class": "database", "parent": "Payment Processing", "business_service": "Retail Banking Platform", "description": "Payment transaction store"},

        # Messaging
        {"name": "Event Bus (Kafka)", "ci_class": "message_queue", "parent": "Retail Banking Platform", "business_service": "Retail Banking Platform", "description": "Event streaming backbone"},

        # Infrastructure
        {"name": "Banking App Hosts", "ci_class": "linux_host", "parent": "Account Service", "business_service": "Retail Banking Platform", "description": "Application server fleet"},
    ],

    "healthcare": [
        {"name": "Patient Care Platform", "ci_class": "cmdb_ci_service", "parent": "", "business_service": "Patient Care Platform", "description": "Integrated patient care system"},

        {"name": "Patient Portal", "ci_class": "web_server", "parent": "Patient Care Platform", "business_service": "Patient Care Platform", "description": "Patient self-service portal"},
        {"name": "Clinical Workstation API", "ci_class": "api_gateway", "parent": "Patient Care Platform", "business_service": "Patient Care Platform", "description": "Clinician workflow API gateway"},
        {"name": "EMR Service", "ci_class": "app_server", "parent": "Patient Care Platform", "business_service": "Patient Care Platform", "description": "Electronic medical records"},
        {"name": "Claims Processing Engine", "ci_class": "app_server", "parent": "Patient Care Platform", "business_service": "Patient Care Platform", "description": "Insurance claims processing"},
        {"name": "Lab Results Service", "ci_class": "app_server", "parent": "Patient Care Platform", "business_service": "Patient Care Platform", "description": "Lab result integration"},
        {"name": "Patient Identity & Auth", "ci_class": "auth_service", "parent": "Patient Care Platform", "business_service": "Patient Care Platform", "description": "Patient and provider auth"},

        {"name": "EMR Database", "ci_class": "database", "parent": "EMR Service", "business_service": "Patient Care Platform", "description": "HL7 FHIR data store"},
        {"name": "Claims Database", "ci_class": "database", "parent": "Claims Processing Engine", "business_service": "Patient Care Platform", "description": "Claims transaction DB"},

        {"name": "HL7 Message Queue", "ci_class": "message_queue", "parent": "Patient Care Platform", "business_service": "Patient Care Platform", "description": "HL7 ADT/ORM message broker"},
        {"name": "Clinical App Hosts", "ci_class": "linux_host", "parent": "EMR Service", "business_service": "Patient Care Platform", "description": "Clinical application servers"},
    ],

    "retail": [
        {"name": "E-Commerce Platform", "ci_class": "cmdb_ci_service", "parent": "", "business_service": "E-Commerce Platform", "description": "Omnichannel retail platform"},

        {"name": "Storefront Web", "ci_class": "web_server", "parent": "E-Commerce Platform", "business_service": "E-Commerce Platform", "description": "Customer-facing storefront"},
        {"name": "Commerce API Gateway", "ci_class": "api_gateway", "parent": "E-Commerce Platform", "business_service": "E-Commerce Platform", "description": "API gateway for commerce services"},
        {"name": "Product Catalog Service", "ci_class": "app_server", "parent": "E-Commerce Platform", "business_service": "E-Commerce Platform", "description": "Product and pricing service"},
        {"name": "Order Management Service", "ci_class": "app_server", "parent": "E-Commerce Platform", "business_service": "E-Commerce Platform", "description": "Order lifecycle management"},
        {"name": "Inventory Service", "ci_class": "app_server", "parent": "E-Commerce Platform", "business_service": "E-Commerce Platform", "description": "Real-time inventory tracking"},
        {"name": "Payment Gateway", "ci_class": "payment_processor", "parent": "E-Commerce Platform", "business_service": "E-Commerce Platform", "description": "Checkout and payment processing"},
        {"name": "Fraud Prevention", "ci_class": "fraud_detection", "parent": "E-Commerce Platform", "business_service": "E-Commerce Platform", "description": "Order fraud scoring"},

        {"name": "Product DB", "ci_class": "database", "parent": "Product Catalog Service", "business_service": "E-Commerce Platform", "description": "Product catalog DB"},
        {"name": "Order DB", "ci_class": "database", "parent": "Order Management Service", "business_service": "E-Commerce Platform", "description": "Order and fulfillment DB"},

        {"name": "Order Event Stream", "ci_class": "message_queue", "parent": "E-Commerce Platform", "business_service": "E-Commerce Platform", "description": "Order events Kafka topic"},
        {"name": "Commerce App Cluster", "ci_class": "kubernetes", "parent": "E-Commerce Platform", "business_service": "E-Commerce Platform", "description": "K8s cluster for commerce microservices"},
    ],

    "telecom": [
        {"name": "Subscriber Platform", "ci_class": "cmdb_ci_service", "parent": "", "business_service": "Subscriber Platform", "description": "Telecoms subscriber management"},

        {"name": "Self-Service Portal", "ci_class": "web_server", "parent": "Subscriber Platform", "business_service": "Subscriber Platform", "description": "My Account portal"},
        {"name": "BSS API Gateway", "ci_class": "api_gateway", "parent": "Subscriber Platform", "business_service": "Subscriber Platform", "description": "BSS northbound API"},
        {"name": "Subscriber Management", "ci_class": "app_server", "parent": "Subscriber Platform", "business_service": "Subscriber Platform", "description": "Subscriber lifecycle and CRM"},
        {"name": "Billing Engine", "ci_class": "app_server", "parent": "Subscriber Platform", "business_service": "Subscriber Platform", "description": "Rating and billing"},
        {"name": "Network Provisioning", "ci_class": "app_server", "parent": "Subscriber Platform", "business_service": "Subscriber Platform", "description": "Service activation and provisioning"},
        {"name": "Auth & SSO", "ci_class": "auth_service", "parent": "Subscriber Platform", "business_service": "Subscriber Platform", "description": "Subscriber authentication"},

        {"name": "Subscriber DB", "ci_class": "database", "parent": "Subscriber Management", "business_service": "Subscriber Platform", "description": "Subscriber master data"},
        {"name": "Billing DB", "ci_class": "database", "parent": "Billing Engine", "business_service": "Subscriber Platform", "description": "CDR and billing records"},

        {"name": "BSS Event Bus", "ci_class": "message_queue", "parent": "Subscriber Platform", "business_service": "Subscriber Platform", "description": "Event-driven BSS integration bus"},
        {"name": "BSS App Hosts", "ci_class": "linux_host", "parent": "Billing Engine", "business_service": "Subscriber Platform", "description": "BSS application servers"},
    ],

    "manufacturing": [
        {"name": "Smart Factory Platform", "ci_class": "cmdb_ci_service", "parent": "", "business_service": "Smart Factory Platform", "description": "Manufacturing operations platform"},

        {"name": "MES Web Dashboard", "ci_class": "web_server", "parent": "Smart Factory Platform", "business_service": "Smart Factory Platform", "description": "Manufacturing execution dashboard"},
        {"name": "MES API Layer", "ci_class": "api_gateway", "parent": "Smart Factory Platform", "business_service": "Smart Factory Platform", "description": "MES northbound API"},
        {"name": "MES Core Service", "ci_class": "app_server", "parent": "Smart Factory Platform", "business_service": "Smart Factory Platform", "description": "Manufacturing execution engine"},
        {"name": "ERP Integration Service", "ci_class": "app_server", "parent": "Smart Factory Platform", "business_service": "Smart Factory Platform", "description": "SAP/ERP integration layer"},
        {"name": "Quality Management", "ci_class": "app_server", "parent": "Smart Factory Platform", "business_service": "Smart Factory Platform", "description": "QMS and SPC tracking"},

        {"name": "Production DB", "ci_class": "database", "parent": "MES Core Service", "business_service": "Smart Factory Platform", "description": "Production order and BOM DB"},
        {"name": "Quality DB", "ci_class": "database", "parent": "Quality Management", "business_service": "Smart Factory Platform", "description": "Quality records and defect tracking"},

        {"name": "Factory Event Bus", "ci_class": "message_queue", "parent": "Smart Factory Platform", "business_service": "Smart Factory Platform", "description": "SCADA/IoT event streaming"},
        {"name": "Factory Servers", "ci_class": "linux_host", "parent": "MES Core Service", "business_service": "Smart Factory Platform", "description": "On-premise factory servers"},
    ],

    "generic": [
        {"name": "Application Platform", "ci_class": "cmdb_ci_service", "parent": "", "business_service": "Application Platform", "description": "3-tier web application"},

        {"name": "Web Tier", "ci_class": "web_server", "parent": "Application Platform", "business_service": "Application Platform", "description": "Frontend web servers"},
        {"name": "API Gateway", "ci_class": "api_gateway", "parent": "Application Platform", "business_service": "Application Platform", "description": "API management layer"},
        {"name": "Application Tier", "ci_class": "app_server", "parent": "Application Platform", "business_service": "Application Platform", "description": "Business logic tier"},
        {"name": "Auth Service", "ci_class": "auth_service", "parent": "Application Platform", "business_service": "Application Platform", "description": "Authentication and authorization"},

        {"name": "Primary Database", "ci_class": "database", "parent": "Application Tier", "business_service": "Application Platform", "description": "Primary data store"},
        {"name": "Cache Layer", "ci_class": "database", "parent": "Application Tier", "business_service": "Application Platform", "description": "Redis/Memcached caching tier"},

        {"name": "Message Bus", "ci_class": "message_queue", "parent": "Application Platform", "business_service": "Application Platform", "description": "Async messaging layer"},
        {"name": "App Hosts", "ci_class": "linux_host", "parent": "Application Tier", "business_service": "Application Platform", "description": "Application server fleet"},
    ],
}


def get_vertical(name: str) -> list[dict]:
    key = name.lower().strip()
    if key not in VERTICALS:
        available = ", ".join(VERTICALS.keys())
        raise ValueError(f"Unknown vertical '{name}'. Available: {available}")
    return VERTICALS[key]


def list_verticals() -> list[str]:
    return list(VERTICALS.keys())
