FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias para compilar Squid con SSL
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libcap-dev \
    libltdl-dev \
    libxml2-dev \
    libnetfilter-conntrack-dev \
    libexpat1-dev \
    libldap2-dev \
    libpam0g-dev \
    libdb-dev \
    libsasl2-dev \
    libkrb5-dev \
    pkg-config \
    wget \
    ca-certificates \
    apache2-utils \
    ldap-utils \
    openssl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Instalar librerías Python para el helper de autenticación (local bcrypt + LDAP)
RUN pip3 install --no-cache-dir --break-system-packages bcrypt==4.2.1 ldap3==2.9.1

# Descargar y compilar Squid 6.12 con soporte SSL Bump (OpenSSL)
RUN wget -q "http://www.squid-cache.org/Versions/v6/squid-6.12.tar.gz" -O /tmp/squid.tar.gz \
    && ls -la /tmp/squid.tar.gz \
    && cd /tmp && tar xzf squid.tar.gz \
    && cd squid-6.12 \
    && ./configure \
        --prefix=/usr \
        --sysconfdir=/etc/squid \
        --libexecdir=/usr/lib/squid \
        --localstatedir=/var \
        --datadir=/usr/share/squid \
        --with-default-user=proxy \
        --with-openssl \
        --enable-ssl-crtd \
        --enable-auth-basic=NCSA,LDAP,DB,getpwnam,fake \
        --enable-auth-digest=file,LDAP \
        --enable-delay-pools \
        --enable-icap-client \
        --enable-follow-x-forwarded-for \
        --enable-storeio=ufs,aufs,diskd,rock \
        --enable-removal-policies=lru,heap \
        --enable-cache-digests \
        --enable-linux-netfilter \
        --with-filedescriptors=65536 \
        --with-large-files \
    && make -j1 \
    && make install \
    && cp /tmp/squid-6.12/src/mime.conf /etc/squid/mime.conf 2>/dev/null || true \
    && mkdir -p /usr/share/squid/icons /usr/share/squid/errors \
    && cp -r /tmp/squid-6.12/icons/* /usr/share/squid/icons/ 2>/dev/null || true \
    && cp -r /tmp/squid-6.12/errors/* /usr/share/squid/errors/ 2>/dev/null || true \
    && cd / && rm -rf /tmp/squid* \
    && id proxy || useradd -r -s /usr/sbin/nologin proxy

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copiar el helper de autenticación personalizado (local + LDAP)
COPY auth_helper.py /usr/lib/squid/squidmanager_auth_helper
RUN chmod +x /usr/lib/squid/squidmanager_auth_helper

# Guardar copia de archivos de config en /opt/squid-defaults/ (el volumen /etc/squid los ocultara)
RUN mkdir -p /opt/squid-defaults && cp /etc/squid/mime.conf /opt/squid-defaults/ 2>/dev/null || true \
    && cp /etc/squid/mime.conf.default /opt/squid-defaults/ 2>/dev/null || true \
    && cp /etc/squid/errorpage.css /opt/squid-defaults/ 2>/dev/null || true \
    && cp /etc/squid/cachemgr.conf /opt/squid-defaults/ 2>/dev/null || true \
    && cp /etc/squid/squid.conf.documented /opt/squid-defaults/ 2>/dev/null || true \
    && cp -r /usr/share/squid/icons /opt/squid-defaults/ 2>/dev/null || true \
    && cp -r /usr/share/squid/errors /opt/squid-defaults/ 2>/dev/null || true \
    && cp /usr/share/squid/mib.txt /opt/squid-defaults/ 2>/dev/null || true

RUN mkdir -p /var/spool/squid /var/log/squid /etc/squid/ssl_cert /var/lib/ssl_crtd
RUN chown -R proxy:proxy /var/spool/squid /var/log/squid /etc/squid/ssl_cert /var/lib/ssl_crtd 2>/dev/null || true

EXPOSE 3128

ENTRYPOINT ["/entrypoint.sh"]