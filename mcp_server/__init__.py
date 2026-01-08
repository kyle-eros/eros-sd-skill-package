"""EROS MCP Server Package.

Provides database access tools for the EROS Schedule Generator.
Server: eros-db
Tools: 15 total

Tool Categories:
  - Creator (5): get_creator_profile, get_active_creators, get_allowed_content_types,
                 get_content_type_rankings, get_persona_profile
  - Schedule (5): get_volume_config, get_active_volume_triggers, get_performance_trends,
                  save_schedule, save_volume_triggers
  - Caption (3): get_batch_captions_by_content_types, get_send_type_captions,
                 validate_caption_structure
  - Config (2): get_send_types, get_send_types_constraints

Optimization Note:
  Use get_send_types_constraints for schedule generation (~2k tokens).
  Use get_send_types only when full details needed (~14.6k tokens).
"""
__version__ = "1.1.0"
__server_name__ = "eros-db"
