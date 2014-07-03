FROM wordtree/python-flask

ADD app /opt/annotateit/

WORKDIR /opt/annotateit/

ENV SECRET_KEY annotateit-change-me
ENV RECAPTCHA_PUBLIC_KEY annotateit-change-me
ENV RECAPTCHA_PRIVATE_KEY annotateit-change-me

VOLUME ["/data"]

EXPOSE 5000

CMD ./run.sh