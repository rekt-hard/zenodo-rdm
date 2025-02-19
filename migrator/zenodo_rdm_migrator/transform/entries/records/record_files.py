# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 CERN.
#
# ZenodoRDM is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Zenodo migrator metadata entry transformer."""

from invenio_rdm_migrator.streams.records.transform import RDMRecordFileEntry


class ZenodoRDMRecordFileEntry(RDMRecordFileEntry):
    """Transform a single record file entry.

    Connects records with files.
    """

    def __init__(self, context):
        """Constructor."""
        self.context = context

    def _created(self, entry):
        """Returns the creation date."""
        # use record created date
        return self.context["created"]

    def _updated(self, entry):
        """Returns the update date."""
        # use record updated date
        return self.context["updated"]

    def _json(self, entry):
        """Returns the rdm record file metadata."""
        return {}

    def _version_id(self, entry):
        """Returns the rdm record file version."""
        # we hardcode version to 1 as this is used for optimistic concurrency checks
        return 1

    def _key(self, entry):
        """Returns the rdm record file key name."""
        return entry["key"]

    def _object_version_id(self, entry):
        """Returns the associated file object version ID."""
        return entry["version_id"]
