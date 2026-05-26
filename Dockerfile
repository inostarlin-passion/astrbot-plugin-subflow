# syntax=docker/dockerfile:1
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先装依赖（pyproject + 包源码），后续运行时数据走挂载卷
COPY pyproject.toml README.md ./
COPY nonebot_plugin_subflow ./nonebot_plugin_subflow
COPY bot.py ./

RUN pip install --no-cache-dir .

# 运行时挂载点：bindings.json / pipelines.json / episode_pipelines.json
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8080

CMD ["python", "bot.py"]
