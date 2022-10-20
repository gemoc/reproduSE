FROM jupyterhub/jupyterhub:3.0

RUN apt-get update -y && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

RUN pip install dockerspawner \
                jupyterhub-idle-culler \
                oauthenticator \
                psycopg2-binary

COPY jupyterhub_config.py /etc/jupyterhub/
COPY artifacts.json /etc/jupyterhub/
COPY templates /etc/jupyterhub/templates

ENTRYPOINT ["jupyterhub"]
CMD ["-f", "/etc/jupyterhub/jupyterhub_config.py"]
