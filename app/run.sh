#!/bin/bash
cd /opt/annotateit

export ELASTICSEARCH_HOST="http://$ES_PORT_9200_TCP_ADDR:$ES_PORT_9200_TCP_PORT"

echo "Waiting for ElasticSearch at $ELASTICSEARCH_HOST ..."
while ! curl $ELASTICSEARCH_HOST
do
  echo "$(date) - still trying"
  sleep 1
done
echo "$(date) - connected successfully"

if [ ! -f .bootstrapped ]; then
    python bootstrap.py && touch .bootstrapped
fi

python run.py | grep -v DeprecationWarning