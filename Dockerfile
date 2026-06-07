ARG VERSION=0.4.0

FROM python:3.12-slim AS build

WORKDIR /app

COPY pyproject.toml README.md ./
COPY community_ai_audit/ community_ai_audit/

RUN pip install --no-cache-dir build wheel && \
    pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir .

FROM python:3.12-slim AS runtime

ARG VERSION

LABEL maintainer="Community Contributors"
LABEL description="Community-driven AI security audit tool using interpretability techniques"
LABEL version="${VERSION}"

WORKDIR /app

COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

ENV COMMUNITY_AI_AUDIT_CONFIG=/app/config/default.yaml

ENTRYPOINT ["community-ai-audit"]
