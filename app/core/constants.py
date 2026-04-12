"""Defines constants for the application."""

from app.agent.state import AgentStack

# Issue States
# These values correspond to what we read and want to write (before formatting).
ISSUE_STATE_OPEN = "Open"
ISSUE_STATE_IN_REVIEW = "In Review"
ISSUE_STATE_IN_PROGRESS = "In Progress"
ISSUE_STATE_DONE = "Done"

LLM_PROVIDER_API_ENV = {
    "mistral": "MISTRAL_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "ollama": "OLLAMA_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

TECH_STACKS = {
    AgentStack.BACKEND: {
        "language": "Java 21",
        "framework": "Spring Boot 3.2 (Web, JPA)",
        "build_tool": "Maven",
        "database": "PostgreSQL",
        "other": ["Lombok"],
        "scripts": {
            "test": "mvn clean test",
            "verify": "mvn verify",
            "build": "mvn clean package",
            "run": "mvn spring-boot:run",
        },
        "test_patterns": {
            "unit": ["*Test.java"],
            "integration": ["*IT.java"],
            "all": ["*Test.java", "*IT.java"],
        },
    },
    AgentStack.GRADLE_NODE: {
        "language": "Java 21",
        "framework": "Spring Boot 3.3 (multi-module Gradle)",
        "build_tool": "Gradle",
        "database": "Configurable (Redis/Postgres/MySQL/etc.)",
        "other": [
            "Lombok",
            "Log4j2",
            "JUnit Platform",
            "Spotless",
        ],
        "scripts": {
            "test": "./gradlew clean test",
            "verify": "./gradlew check",
            "build": "./gradlew build",
            "run": "cd server && ../gradlew bootRun",
        },
        "test_patterns": {
            "unit": ["*Test.java"],
            "integration": ["*IT.java"],
            "all": ["*Test.java", "*IT.java"],
        },
    },
    AgentStack.FRONTEND: {
        "language": "JavaScript (ES6+) / TypeScript",
        "framework": "React (Functional Components, Hooks)",
        "build_tool": "Vite",
        "structure": "HTML5 (Semantic)",
        "other": ["Bootstrap 5 CSS"],
        "scripts": {
            "test": "npm test",
            "verify": "npm test",
            "build": "npm run build",
            "run": "npm run dev",
        },
        "test_patterns": {
            "unit": ["*.test.js", "*.test.jsx", "*.test.ts", "*.test.tsx"],
            "integration": ["*.integration.test.js", "*.integration.test.ts"],
            "all": ["*.test.js", "*.test.jsx", "*.test.ts", "*.test.tsx", "*.spec.js", "*.spec.ts"],
        },
    },
}
