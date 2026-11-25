# syntax=docker/dockerfile:1.7
FROM eclipse-temurin:21-jre@sha256:d77e090ae1f6970c047b443c6f0a6c1358b0426d44432bb5a7753408cd43de0d

RUN mkdir -p -m 755 /opt/synthea

# Synthea v4.0.0 release jar, verified against its SHA-256 at build time.
ADD --chmod=644 --checksum=sha256:ed43c20ad40ba5c3bc724503a5af032715fe3c491620b766148e7c2361e6ecc1 \
    https://github.com/synthetichealth/synthea/releases/download/v4.0.0/synthea-with-dependencies.jar \
    /opt/synthea/synthea.jar

WORKDIR /tmp
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "/opt/synthea/synthea.jar"]
