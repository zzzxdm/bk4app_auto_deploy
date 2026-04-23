FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app

# 设置时区为北京
ENV TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y tzdata \
    && ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && apt-get clean

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "scheduler.py"]