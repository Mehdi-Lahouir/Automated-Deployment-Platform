FROM postgres:18-alpine

RUN apk add --no-cache restic \
    && addgroup -S -g 10001 backup \
    && adduser -S -D -H -u 10001 -G backup backup \
    && mkdir -p /work /restore /repository \
    && chown -R backup:backup /work /restore /repository

COPY --chown=backup:backup backup/entrypoint.sh backup/run-backup.sh backup/run-restore.sh /usr/local/bin/
RUN chmod 0555 /usr/local/bin/entrypoint.sh /usr/local/bin/run-backup.sh /usr/local/bin/run-restore.sh

USER 10001:10001
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
