FROM python:3.11

ENV PYTHON_VERSION=3.11
RUN apt-get update && apt-get install -y --no-install-recommends \
		python${PYTHON_VERSION}-venv \
    	python${PYTHON_VERSION}-dev \
    	default-libmysqlclient-dev \
    	build-essential \
    	pkg-config \
        && rm -rf /var/lib/apt/lists/* \

WORKDIR /opt/aios
COPY ./src /opt/aios
COPY ./rootfs /opt/aios/app

RUN mkdir -p /root/myai/app
RUN mkdir -p /root/myai/data
RUN mkdir -p /root/myai/etc

RUN pip install --no-cache-dir -r /opt/aios/requirements.txt

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

CMD ["python3","./service/aios_shell/aios_shell.py"]
