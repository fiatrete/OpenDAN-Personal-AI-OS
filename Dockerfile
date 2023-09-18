FROM python:3.11
WORKDIR /opt/aios
COPY ./src /opt/aios
COPY ./rootfs /var/aios
RUN pip install --no-cache-dir -r /opt/opendan/requirements.txt

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

CMD ["python3","./service/aios_shell/aios_shell.py"]