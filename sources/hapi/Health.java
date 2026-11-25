import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/**
 * Container healthcheck for the distroless HAPI FHIR image, which has no shell or curl.
 * Exits 0 only when the FHIR capability statement answers HTTP 200.
 */
public final class Health {
    private Health() {}

    public static void main(String[] args) {
        String url = args.length > 0 ? args[0] : "http://localhost:8080/fhir/metadata";
        try {
            HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
            HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(8))
                    .header("Accept", "application/fhir+json")
                    .GET()
                    .build();
            int status = client.send(request, HttpResponse.BodyHandlers.discarding()).statusCode();
            System.exit(status == 200 ? 0 : 1);
        } catch (Exception e) {
            System.err.println("health check failed: " + e);
            System.exit(1);
        }
    }
}
