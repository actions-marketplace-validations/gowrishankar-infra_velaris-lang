# Velaris, ready to run.
#
#   docker build -t velaris .
#   docker run --rm -v "$PWD:/work" velaris check /work/main.vel
#   docker run --rm -v "$PWD:/work" velaris /work/main.vel
#
# The image carries the prover and the native backend, so promises are
# proven rather than checked while running.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="Velaris"
LABEL org.opencontainers.image.description="A language where signatures declare types, effects, and machine-checked promises."
LABEL org.opencontainers.image.source="https://github.com/gowrishankar-infra/velaris-lang"
LABEL org.opencontainers.image.licenses="MIT"

RUN pip install --no-cache-dir "velaris-lang[full]" && velaris doctor

WORKDIR /work
ENTRYPOINT ["velaris"]
CMD ["--version"]
