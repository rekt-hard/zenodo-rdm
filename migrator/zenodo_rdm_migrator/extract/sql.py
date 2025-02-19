# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 CERN.
#
# ZenodoRDM is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Migrator SQL extraction."""


EXTRACT_USERS_SQL = """
COPY (
    SELECT row_to_json(users)
    FROM (
        SELECT
            u.*,
            up.*,
            coalesce(user_t.tokens, null) AS tokens,
            coalesce(user_i.identities, null) AS identities,
            coalesce(user_sa.session_activity, null) AS session_activity
        FROM accounts_user AS u
        LEFT JOIN userprofiles_userprofile up ON u.id = up.user_id
        LEFT JOIN LATERAL (
            SELECT json_agg(row_to_json(_t)) AS tokens
            FROM (
                SELECT t.*, c.name
                FROM oauth2server_token AS t
                JOIN oauth2server_client c ON t.client_id = c.client_id
                WHERE t.user_id = u.id
                    AND t.is_personal = true
                    AND t.is_internal = false
            ) as _t
        ) AS user_t ON true
        LEFT JOIN LATERAL (
            SELECT json_agg(row_to_json(i)) AS identities
            FROM oauthclient_useridentity AS i
            WHERE i.id_user = u.id
        ) AS user_i ON true
        LEFT JOIN LATERAL (
            SELECT json_agg(row_to_json(sa)) AS session_activity
            FROM accounts_user_session_activity AS sa
            WHERE sa.user_id = u.id
        ) AS user_sa ON true
    ) as users
) TO STDOUT;
"""

EXTRACT_RECORDS_SQL = """
COPY (
    SELECT row_to_json(records)
    FROM (
        SELECT
            r.*, pr.index
        FROM records_metadata as r
            JOIN pidstore_pid
                ON pidstore_pid.object_uuid = r.id
            JOIN pidrelations_pidrelation as pr
                ON pidstore_pid.id = pr.child_id
        WHERE
            pidstore_pid.pid_type = 'recid' AND
            pidstore_pid.status = 'R' AND
            pidstore_pid.object_type = 'rec'
    ) as records
) TO STDOUT;
"""

EXTRACT_DRAFTS_SQL = """
COPY (
    SELECT row_to_json(deposits)
    FROM (
        SELECT
            r.*
        FROM records_metadata as r
            JOIN pidstore_pid
                ON pidstore_pid.object_uuid = r.id
        WHERE
            pidstore_pid.pid_type = 'depid' AND
            pidstore_pid.status = 'R' AND
            pidstore_pid.object_type = 'rec'
    ) as deposits
) TO STDOUT;
"""

EXTRACT_REQUESTS_SQL = """
COPY (
    SELECT row_to_json(requests)
    FROM (
        WITH active_communities AS (
            SELECT DISTINCT(id_community) FROM communities_community_record
                INNER JOIN communities_community ON id_community=id
                WHERE id_community NOT IN ('zenodo', 'ecfunded')
                    AND deleted_at IS NULL
        ), records_ir AS (
            SELECT
                cr.created,
                cr.updated,
                (r.json->>'conceptrecid')::character varying AS conceptrecid,
                (r.json->>'recid')::character varying AS recid,
                cr.id_community,
                (r.json#>>'{owners, 0}')::character varying AS owners,
                (r.json->>'title')::character varying AS title
            FROM records_metadata AS r INNER JOIN communities_community_record AS cr
                ON id_record = id
                WHERE id_community NOT IN ('zenodo', 'ecfunded')
                    AND r.json->>'conceptrecid' IS NOT NULL
        ), records_pid AS (
            SELECT
                records_ir.created,
                records_ir.updated,
                records_ir.id_community,
                records_ir.conceptrecid,
                records_ir.recid,
                pidstore_pid.id as pid_id,
                records_ir.owners,
                records_ir.title
            FROM pidstore_pid INNER JOIN records_ir
                ON pid_value=records_ir.recid
                WHERE pid_type='recid' AND status!= 'D'
        ), records_index AS (
            SELECT
                records_pid.created,
                records_pid.updated,
                records_pid.id_community,
                records_pid.conceptrecid,
                records_pid.recid,
                pr.index,
                records_pid.owners,
                records_pid.title
            FROM records_pid INNER JOIN pidrelations_pidrelation AS pr
                ON pid_id = pr.child_id
        ), concept_last_version AS (
            SELECT conceptrecid, MAX(index) as max_index
            FROM records_index GROUP BY conceptrecid
        ), active_records AS (
            SELECT
                created,
                updated,
                id_community,
                ri.conceptrecid,
                recid,
                owners,
                title
            FROM records_index AS ri INNER JOIN concept_last_version AS clv
            ON ri.conceptrecid = clv.conceptrecid AND index = max_index
        )
        SELECT
            ar.created,
            ar.updated,
            ac.id_community,
            ar.conceptrecid,
            ar.recid,
            ar.owners,
            ar.title
        FROM active_records AS ar INNER JOIN active_communities AS ac
            ON ar.id_community=ac.id_community
    ) as requests
) TO STDOUT;
"""

EXTRACT_COMMUNITIES_SQL = """
COPY (
    WITH last_featured_comms AS (
        SELECT
            id_community as id,
            MAX(start_date) as start_date,
            MAX(created) as created,
            MAX(updated) as updated
        FROM communities_featured_community AS fc
        GROUP BY id_community
    )
    SELECT
        row_to_json(communities)
    FROM
        (
            SELECT
                c.*,
                CASE
                    WHEN fc.start_date IS NULL THEN FALSE
                    ELSE TRUE
                END as is_featured,
                fc.start_date as featured_start_date,
                fc.created as featured_created,
                fc.updated as featured_updated,
                ff.id as logo_file_id
            FROM
                communities_community as c
                LEFT OUTER JOIN last_featured_comms as fc ON c.id = fc.id
                LEFT OUTER JOIN files_object as fo ON
                    fo.key = c.id || '/logo.' || c.logo_ext
                    AND c.logo_ext IS NOT NULL
                    AND fo.bucket_id = '00000000-0000-0000-0000-000000000000'
                    AND fo.is_head
                LEFT OUTER JOIN files_files as ff ON fo.file_id = ff.id
            WHERE
                c.deleted_at IS NULL
        ) as communities
) TO STDOUT;
"""

# NOTE: We're using a binary export for the files tables, since we're not filtering
EXTRACT_FILE_INSTANCES_SQL = """
COPY (
  SELECT
      id,
      created,
      updated,
      uri,
      'L' as storage_class,
      size,
      checksum,
      readable,
      writable,
      last_check_at,
      last_check
  FROM files_files
) TO STDOUT WITH (FORMAT binary);
"""
EXTRACT_FILE_BUCKETS_SQL = """
COPY (
  SELECT
      id,
      created,
      updated,
      default_location,
      'L' as default_storage_class,
      size,
      quota_size,
      max_file_size,
      locked,
      deleted
  FROM files_bucket
) TO STDOUT WITH (FORMAT binary);
"""
EXTRACT_FILE_OBJECT_VERSIONS_SQL = """
COPY (
  SELECT
      version_id,
      created,
      updated,
      key,
      bucket_id,
      file_id,
      _mimetype,
      is_head
  FROM files_object
) TO STDOUT WITH (FORMAT binary);
"""

EXTRACT_DEPOSITS_SQL = """
COPY (
    SELECT row_to_json(deposits)
    FROM (
        SELECT
            r.*
        FROM records_metadata as r
            JOIN pidstore_pid
                ON pidstore_pid.object_uuid = r.id
        WHERE
            pidstore_pid.pid_type = 'depid' AND
            pidstore_pid.status = 'R' AND
            pidstore_pid.object_type = 'rec'
    ) as deposits
) TO STDOUT;
"""

EXTRACT_OAUTH_2_SERVER_TOKENS = """
COPY (
    SELECT row_to_json(tokens)
    FROM (
        SELECT
            id,
            client_id,
            user_id,
            token_type,
            convert_from(access_token, "utf-8") as access_token,
            convert_from(refresh_token, "utf-8") as refresh_token,
            expires,
            _scopes,
            is_personal,
            is_internal
        FROM oauth2server_token
        WHERE
             user_id=57245
    ) as tokens
    LIMIT 100000
) TO STDOUT;
"""
