# Build stage: compile the healthcheck, because the HAPI image is distroless (no shell or curl).
FROM eclipse-temurin:21-jdk@sha256:8ad118b146aa92da815b576441acd6b42b38236797ad0b6edc8c200b85bb0734 AS build
COPY Health.java /src/Health.java
RUN javac --release 21 -d /out /src/Health.java

FROM hapiproject/hapi:v8.12.0-2@sha256:0ff86aac4c7bd13a1ee226444a70263bb46ed1c28ef543c30a44f865b80ca04e
COPY --from=build /out/Health.class /opt/hdp/health/Health.class
