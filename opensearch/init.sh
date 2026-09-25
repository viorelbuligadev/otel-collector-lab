#!/bin/sh
# Prepares OpenSearch and Dashboards before the collector sends any log:
#   1. installs the index template (settings + field types for *-log-producer and unrouted)
#   2. creates one index per app plus "unrouted"; the template is applied to each at creation
#   3. creates the Dashboards index patterns, so Discover works right away
# Safe to run again: the template and index patterns are overwritten, existing indices are left untouched.
set -eu

OS=http://opensearch:9200
OSD=http://opensearch-dashboards:5601
INDICES="dotnet-log-producer python-log-producer unrouted"

echo "== Index template: log-producers"
curl -sS --fail-with-body -X PUT "$OS/_index_template/log-producers" \
  -H "Content-Type: application/json" --data-binary @/opensearch/index-template-log-producers.json
echo

for index in $INDICES; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "$OS/$index")
  if [ "$status" = "200" ]; then
    echo "== Index $index: already exists"
  else
    echo "== Index $index: creating"
    curl -sS --fail-with-body -X PUT "$OS/$index"   # no body: settings and mappings come from the template
    echo
  fi
done

# index_pattern <id> <title>
# The id is fixed, so ?overwrite=true updates the same pattern instead of adding a duplicate.
index_pattern() {
  echo "== Index pattern: $2"
  curl -sS --fail-with-body -X POST "$OSD/api/saved_objects/index-pattern/$1?overwrite=true" \
    -H "Content-Type: application/json" -H "osd-xsrf: true" \
    -d "{\"attributes\":{\"title\":\"$2\",\"timeFieldName\":\"@timestamp\"}}" -o /dev/null
}

index_pattern all-log-producers "*-log-producer"   # both apps together
for index in $INDICES; do
  index_pattern "$index" "$index"                   # one per app
done

echo "== Default index pattern: *-log-producer"
curl -sS --fail-with-body -X POST "$OSD/api/opensearch-dashboards/settings" \
  -H "Content-Type: application/json" -H "osd-xsrf: true" \
  -d '{"changes":{"defaultIndex":"all-log-producers"}}' -o /dev/null

echo "== Done"
