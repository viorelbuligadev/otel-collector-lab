using Microsoft.Extensions.Logging;
using OpenTelemetry.Exporter;
using OpenTelemetry.Logs;
using OpenTelemetry.Resources;

// The OTLP exporter sends to http://localhost:4317 (gRPC) by default.
// Override with the OTEL_EXPORTER_OTLP_ENDPOINT environment variable if needed.
using var loggerFactory = LoggerFactory.Create(builder =>
{
    builder.SetMinimumLevel(LogLevel.Debug);
    builder.AddConsole();

    builder.AddOpenTelemetry(options =>
    {
        // Resource attributes identify *who* produced the logs.
        options.SetResourceBuilder(ResourceBuilder.CreateDefault()
            .AddService(serviceName: "dotnet-log-producer",serviceVersion: "1.0.0")
            .AddAttributes([new("deployment.environment", "dev")]));

        options.IncludeFormattedMessage = true; // send the rendered message, not just the template
        options.IncludeScopes = true;           // BeginScope values become attributes

        options.AddOtlpExporter(otlp => otlp.Protocol = OtlpExportProtocol.Grpc);
    });
});

var logger = loggerFactory.CreateLogger("LogProducer");

logger.LogInformation("Log producer started");

var runDuration = TimeSpan.FromMinutes(2);
var orderInterval = TimeSpan.FromSeconds(3);

var random = new Random();
var stopAt = DateTime.UtcNow + runDuration;
using var timer = new PeriodicTimer(orderInterval);

for (var orderId = 1; DateTime.UtcNow < stopAt; orderId++)
{
    // Scope values are attached to every log record written inside it.
    using (logger.BeginScope(new Dictionary<string, object> { ["CustomerId"] = $"C-{random.Next(100, 999)}" }))
    {
        var amount = Math.Round(random.NextDouble() * 500, 2);

        // Placeholders like {OrderId} become structured attributes on the OTLP log record.
        logger.LogInformation("Processing order {OrderId} for {Amount} EUR", orderId, amount);

        if (amount > 400)
            logger.LogWarning("Order {OrderId} amount {Amount} exceeds review threshold", orderId, amount);

        if (orderId % 7 == 0)
        {
            try
            {
                throw new InvalidOperationException("Payment gateway timeout");
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Order {OrderId} failed", orderId);
            }
        }

        logger.LogDebug("Order {OrderId} done", orderId);
    }

    await timer.WaitForNextTickAsync();
}

logger.LogInformation("Log producer finished");

// Disposing the LoggerFactory (via `using var` above) flushes batched logs to the collector.
// Without it, the last batch would be lost when the process exits.
