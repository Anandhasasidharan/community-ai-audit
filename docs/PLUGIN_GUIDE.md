# Plugin Guide

## Adding a Model Adapter
Implement `ModelAdapter` or one of its specializations in `community_ai_audit.core.interfaces`.

## Adding a SIEM Connector
Implement `SIEMConnector` if the tool is a SIEM, or `SecurityToolConnector` for broader security integrations.

## Adding a Scanner
Implement `ScannerPlugin.scan(...)` and return a `ScanResult`.

## Adding an Interpreter
Implement `InterpreterPlugin.interpret(...)` and return an `InterpretationResult`.

## Adding a Reporter
Implement `ReporterPlugin.render(...)`.

## Discovery
Place the plugin in a discoverable module or package, or publish it as a package with entry points.