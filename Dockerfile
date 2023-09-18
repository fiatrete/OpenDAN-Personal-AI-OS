FROM python:3.11
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