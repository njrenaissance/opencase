Feature: Distributed tracing — spans delivered to Jaeger
  As an operator running OpenCase on-premise
  I want all API spans sent to the local Jaeger collector
  So that I can observe request traces without sending data off-host

  Background:
    Given the integration stack is running with OTLP tracing enabled

  @integration
  Scenario: Health check span appears in Jaeger
    When I send GET /health to the FastAPI service
    Then Jaeger contains a trace for service "opencase-api"
    And that trace includes a span with operation name containing "GET /health"

  @integration
  Scenario: Readiness check generates a database span
    When I send GET /ready to the FastAPI service
    Then Jaeger contains a trace for service "opencase-api"
    And that trace includes a span with operation name containing "SELECT"
