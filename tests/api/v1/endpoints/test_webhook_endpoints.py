import json

from typing import Dict

import pytest

from fidesops.api.v1.scope_registry import WEBHOOK_READ, WEBHOOK_CREATE_OR_UPDATE
from fidesops.api.v1.urn_registry import (
    V1_URL_PREFIX,
    POLICY_WEBHOOKS_PRE,
    POLICY_WEBHOOKS_POST,
    POLICY_PRE_WEBHOOK_DETAIL,
    POLICY_POST_WEBHOOK_DETAIL,
)
from fidesops.models.policy import PolicyPreWebhook, PolicyPostWebhook
from tests.api.v1.endpoints.test_privacy_request_endpoints import stringify_date


class TestPutPolicyPreExecutionWebhooks:
    @pytest.fixture(scope="function")
    def valid_webhook_request(self, https_connection_config) -> Dict:
        return {
            "connection_config_key": https_connection_config.key,
            "direction": "one_way",
            "name": "Poke Snowflake Webhook",
            "key": "poke_snowflake_webhook",
        }

    @pytest.fixture(scope="function")
    def url(self, policy) -> str:
        return V1_URL_PREFIX + POLICY_WEBHOOKS_PRE.format(policy_key=policy.key)

    def test_put_pre_execution_webhooks_unauthenticated(self, url, api_client):
        resp = api_client.put(url)
        assert resp.status_code == 401

    def test_put_pre_execution_webhooks_wrong_scope(
        self, url, api_client, generate_auth_header
    ):
        auth_header = generate_auth_header(scopes=[WEBHOOK_READ])
        resp = api_client.put(
            url,
            headers=auth_header,
        )
        assert resp.status_code == 403

    def test_invalid_policy(
        self, db, api_client, generate_auth_header, valid_webhook_request
    ):
        url = V1_URL_PREFIX + POLICY_WEBHOOKS_PRE.format(policy_key="my_fake_policy")

        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])
        resp = api_client.put(url, headers=auth_header, json=[valid_webhook_request])

        assert resp.status_code == 404
        body = json.loads(resp.text)
        assert body["detail"] == "No Policy found for key my_fake_policy."
        assert db.query(PolicyPreWebhook).count() == 0  # All must succeed or fail

    def test_invalid_connection_config(
        self, db, url, api_client, generate_auth_header, valid_webhook_request
    ):
        invalid_connection_config_body = {
            "connection_config_key": "unknown_connection_key",
            "direction": "one_way",
            "name": "my_pre_execution_webhook",
        }

        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])
        resp = api_client.put(
            url,
            headers=auth_header,
            json=[valid_webhook_request, invalid_connection_config_body],
        )

        assert resp.status_code == 404
        body = json.loads(resp.text)
        assert (
            body["detail"]
            == "No ConnectionConfig found for key unknown_connection_key."
        )
        assert db.query(PolicyPreWebhook).count() == 0  # All must succeed or fail

    def test_direction_error_fails_all(
        self,
        db,
        https_connection_config,
        generate_auth_header,
        api_client,
        url,
        valid_webhook_request,
    ):
        invalid_connection_config_body = {
            "connection_config_key": https_connection_config.key,
            "direction": "invalid_direction",
            "name": "my_pre_execution_webhook",
        }

        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])
        resp = api_client.put(
            url,
            headers=auth_header,
            json=[valid_webhook_request, invalid_connection_config_body],
        )
        assert resp.status_code == 422
        body = json.loads(resp.text)
        assert (
            body["detail"][0]["msg"]
            == "value is not a valid enumeration member; permitted: 'one_way', 'two_way'"
        )
        assert db.query(PolicyPreWebhook).count() == 0  # All must succeed or fail

    def test_put_pre_execution_webhooks_duplicate_keys(
        self,
        db,
        url,
        api_client,
        generate_auth_header,
        valid_webhook_request,
        https_connection_config,
    ):
        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])
        resp = api_client.put(
            url,
            headers=auth_header,
            json=[valid_webhook_request, valid_webhook_request],
        )
        assert resp.status_code == 400
        body = json.loads(resp.text)
        assert (
            body["detail"]
            == "Check request body: there are multiple webhooks whose keys resolve to the same value."
        )

        name_only = {
            "connection_config_key": https_connection_config.key,
            "direction": "one_way",
            "name": "Poke Snowflake Webhook",
        }

        resp = api_client.put(
            url, headers=auth_header, json=[valid_webhook_request, name_only]
        )
        assert resp.status_code == 400
        body = json.loads(resp.text)
        assert (
            body["detail"]
            == "Check request body: there are multiple webhooks whose keys resolve to the same value."
        )
        assert db.query(PolicyPreWebhook).count() == 0  # All must succeed or fail

    def test_create_multiple_pre_execution_webhooks(
        self,
        db,
        generate_auth_header,
        api_client,
        url,
        valid_webhook_request,
        https_connection_config,
    ):
        second_webhook_body = {
            "connection_config_key": https_connection_config.key,
            "direction": "two_way",
            "name": "My Pre Execution Webhook",
        }
        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])
        resp = api_client.put(
            url,
            headers=auth_header,
            json=[valid_webhook_request, second_webhook_body],
        )
        assert resp.status_code == 200
        body = json.loads(resp.text)
        assert len(body) == 2
        assert body == [
            {
                "direction": "one_way",
                "key": "poke_snowflake_webhook",
                "name": "Poke Snowflake Webhook",
                "connection_config": {
                    "name": https_connection_config.name,
                    "key": "my_webhook_config",
                    "connection_type": "https",
                    "access": "read",
                    "created_at": stringify_date(https_connection_config.created_at),
                    "updated_at": stringify_date(https_connection_config.updated_at),
                    "last_test_timestamp": None,
                    "last_test_succeeded": None,
                },
                "order": 0,
            },
            {
                "direction": "two_way",
                "key": "my_pre_execution_webhook",
                "name": "My Pre Execution Webhook",
                "connection_config": {
                    "name": https_connection_config.name,
                    "key": "my_webhook_config",
                    "connection_type": "https",
                    "access": "read",
                    "created_at": stringify_date(https_connection_config.created_at),
                    "updated_at": stringify_date(https_connection_config.updated_at),
                    "last_test_timestamp": None,
                    "last_test_succeeded": None,
                },
                "order": 1,
            },
        ]

        pre_webhooks = PolicyPreWebhook.filter(
            db=db,
            conditions=(
                PolicyPreWebhook.key.in_(
                    ["my_pre_execution_webhook", "poke_snowflake_webhook"]
                )
            ),
        )

        assert pre_webhooks.count() == 2
        for webhook in pre_webhooks:
            webhook.delete(db=db)

    def test_update_webhooks_reorder(
        self,
        db,
        generate_auth_header,
        api_client,
        url,
        policy_pre_execution_webhooks,
        https_connection_config,
    ):
        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])
        assert policy_pre_execution_webhooks[0].key == "pre_execution_one_way_webhook"
        assert policy_pre_execution_webhooks[0].order == 0
        assert policy_pre_execution_webhooks[1].key == "pre_execution_two_way_webhook"
        assert policy_pre_execution_webhooks[1].order == 1

        # Flip the order in the request
        request_body = [
            {
                "connection_config_key": https_connection_config.key,
                "direction": policy_pre_execution_webhooks[1].direction.value,
                "name": policy_pre_execution_webhooks[1].name,
                "key": policy_pre_execution_webhooks[1].key,
            },
            {
                "connection_config_key": https_connection_config.key,
                "direction": policy_pre_execution_webhooks[0].direction.value,
                "name": policy_pre_execution_webhooks[0].name,
                "key": policy_pre_execution_webhooks[0].key,
            },
        ]

        resp = api_client.put(
            url,
            headers=auth_header,
            json=request_body,
        )
        body = json.loads(resp.text)
        assert body[0]["key"] == "pre_execution_two_way_webhook"
        assert body[0]["order"] == 0
        assert body[1]["key"] == "pre_execution_one_way_webhook"
        assert body[1]["order"] == 1

    def test_update_hooks_remove_hook_from_request(
        self,
        db,
        generate_auth_header,
        api_client,
        url,
        policy_pre_execution_webhooks,
        https_connection_config,
    ):
        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])

        # Only include one hook
        request_body = [
            {
                "connection_config_key": https_connection_config.key,
                "direction": policy_pre_execution_webhooks[0].direction.value,
                "name": policy_pre_execution_webhooks[0].name,
                "key": policy_pre_execution_webhooks[0].key,
            },
        ]

        resp = api_client.put(
            url,
            headers=auth_header,
            json=request_body,
        )
        body = json.loads(resp.text)
        assert len(body) == 1  # Other webhook was removed
        assert body[0]["key"] == "pre_execution_one_way_webhook"
        assert body[0]["order"] == 0


class TestPutPolicyPostExecutionWebhooks:
    """Shares a lot of logic with Pre Execution Webhooks - see TestPutPolicyPreExecutionWebhooks tests"""

    @pytest.fixture(scope="function")
    def valid_webhook_request(self, https_connection_config) -> Dict:
        return {
            "connection_config_key": https_connection_config.key,
            "direction": "one_way",
            "name": "Clear App Cache",
            "key": "clear_app_cache",
        }

    @pytest.fixture(scope="function")
    def url(self, policy) -> str:
        return V1_URL_PREFIX + POLICY_WEBHOOKS_POST.format(policy_key=policy.key)

    def test_put_post_execution_webhooks_unauthenticated(self, url, api_client):
        resp = api_client.put(url)
        assert resp.status_code == 401

    def test_put_post_execution_webhooks_wrong_scope(
        self, url, api_client, generate_auth_header
    ):
        auth_header = generate_auth_header(scopes=[WEBHOOK_READ])
        resp = api_client.put(
            url,
            headers=auth_header,
        )
        assert resp.status_code == 403

    def test_create_multiple_post_execution_webhooks(
        self,
        db,
        generate_auth_header,
        api_client,
        url,
        valid_webhook_request,
        https_connection_config,
    ):
        second_webhook_body = {
            "connection_config_key": https_connection_config.key,
            "direction": "two_way",
            "name": "My Post Execution Webhook",
        }
        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])
        resp = api_client.put(
            url,
            headers=auth_header,
            json=[valid_webhook_request, second_webhook_body],
        )
        assert resp.status_code == 200
        body = json.loads(resp.text)
        assert len(body) == 2
        assert body == [
            {
                "direction": "one_way",
                "key": "clear_app_cache",
                "name": "Clear App Cache",
                "connection_config": {
                    "name": https_connection_config.name,
                    "key": "my_webhook_config",
                    "connection_type": "https",
                    "access": "read",
                    "created_at": stringify_date(https_connection_config.created_at),
                    "updated_at": stringify_date(https_connection_config.updated_at),
                    "last_test_timestamp": None,
                    "last_test_succeeded": None,
                },
                "order": 0,
            },
            {
                "direction": "two_way",
                "key": "my_post_execution_webhook",
                "name": "My Post Execution Webhook",
                "connection_config": {
                    "name": https_connection_config.name,
                    "key": "my_webhook_config",
                    "connection_type": "https",
                    "access": "read",
                    "created_at": stringify_date(https_connection_config.created_at),
                    "updated_at": stringify_date(https_connection_config.updated_at),
                    "last_test_timestamp": None,
                    "last_test_succeeded": None,
                },
                "order": 1,
            },
        ]

        post_webhooks = PolicyPostWebhook.filter(
            db=db,
            conditions=(
                PolicyPostWebhook.key.in_(
                    ["my_post_execution_webhook", "clear_app_cache"]
                )
            ),
        )

        assert post_webhooks.count() == 2
        for webhook in post_webhooks:
            webhook.delete(db=db)


class TestPatchPreExecutionPolicyWebhook:
    """Test updating a single PolicyPreWebhook - however, updates to "order" can affect the orders of other webhooks"""

    @pytest.fixture(scope="function")
    def url(self, policy, policy_pre_execution_webhooks) -> str:
        return V1_URL_PREFIX + POLICY_PRE_WEBHOOK_DETAIL.format(
            policy_key=policy.key, pre_webhook_key=policy_pre_execution_webhooks[0].key
        )

    def test_patch_pre_execution_webhook_unauthenticated(self, url, api_client):
        resp = api_client.patch(url)
        assert resp.status_code == 401

    def test_patch_pre_execution_webhook_wrong_scope(
        self, url, api_client, generate_auth_header
    ):
        auth_header = generate_auth_header(scopes=[WEBHOOK_READ])
        resp = api_client.patch(
            url,
            headers=auth_header,
        )
        assert resp.status_code == 403

    def test_patch_pre_execution_webhook_invalid_webhook_key(
        self, api_client, generate_auth_header, policy
    ):
        return V1_URL_PREFIX + POLICY_PRE_WEBHOOK_DETAIL.format(
            policy_key=policy.key, pre_webhook_key="invalid_webhook_key"
        )

        auth_header = generate_auth_header(scopes=[WEBHOOK_READ])
        resp = api_client.patch(
            url,
            headers=auth_header,
        )
        assert resp.status_code == 404

    def test_path_pre_execution_webhook_invalid_order(
        self, generate_auth_header, api_client, url, policy_pre_execution_webhooks
    ):
        request_body = {"order": 5}
        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])
        resp = api_client.patch(url, headers=auth_header, json=request_body)

        assert resp.status_code == 400
        response_body = json.loads(resp.text)
        assert (
            response_body["detail"]
            == "Cannot set order to 5: there are only 2 PolicyPreWebhook(s) defined on this Policy."
        )

    def test_update_name_only(
        self,
        db,
        generate_auth_header,
        api_client,
        url,
        policy_pre_execution_webhooks,
        https_connection_config,
    ):
        request_body = {"name": "Renaming this webhook"}
        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])
        resp = api_client.patch(url, headers=auth_header, json=request_body)
        assert resp.status_code == 200
        response_body = json.loads(resp.text)
        assert response_body == {
            "resource": {
                "direction": "one_way",
                "key": "pre_execution_one_way_webhook",
                "name": "Renaming this webhook",
                "connection_config": {
                    "name": https_connection_config.name,
                    "key": "my_webhook_config",
                    "connection_type": "https",
                    "access": "read",
                    "created_at": stringify_date(https_connection_config.created_at),
                    "updated_at": stringify_date(https_connection_config.updated_at),
                    "last_test_timestamp": None,
                    "last_test_succeeded": None,
                },
                "order": 0,
            },
            "reordered": [],
        }
        webhook = PolicyPreWebhook.filter(
            db=db, conditions=(PolicyPreWebhook.key == "pre_execution_one_way_webhook")
        ).first()
        assert webhook.order == 0

    def test_update_name_and_order(
        self,
        db,
        generate_auth_header,
        api_client,
        url,
        policy_pre_execution_webhooks,
        https_connection_config,
    ):
        request_body = {"name": "Renaming this webhook", "order": 1}
        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])
        resp = api_client.patch(url, headers=auth_header, json=request_body)
        assert resp.status_code == 200
        response_body = json.loads(resp.text)
        assert response_body == {
            "resource": {
                "direction": "one_way",
                "key": "pre_execution_one_way_webhook",
                "name": "Renaming this webhook",
                "connection_config": {
                    "name": https_connection_config.name,
                    "key": "my_webhook_config",
                    "connection_type": "https",
                    "access": "read",
                    "created_at": stringify_date(https_connection_config.created_at),
                    "updated_at": stringify_date(https_connection_config.updated_at),
                    "last_test_timestamp": None,
                    "last_test_succeeded": None,
                },
                "order": 1,
            },
            "reordered": [
                {"key": "pre_execution_two_way_webhook", "order": 0},
                {"key": "pre_execution_one_way_webhook", "order": 1},
            ],
        }
        webhook = PolicyPreWebhook.filter(
            db=db, conditions=(PolicyPreWebhook.key == "pre_execution_one_way_webhook")
        ).first()
        db.refresh(webhook)
        assert webhook.order == 1


class TestPatchPostExecutionPolicyWebhook:
    """Test updating a single PolicyPostWebhook - however, updates to "order" can affect the orders of other webhooks

    This endpoint shares code with the pre-execution PATCH - see TestPatchPreExecutionPolicyWebhook
    """

    @pytest.fixture(scope="function")
    def url(self, policy, policy_post_execution_webhooks) -> str:
        return V1_URL_PREFIX + POLICY_POST_WEBHOOK_DETAIL.format(
            policy_key=policy.key,
            post_webhook_key=policy_post_execution_webhooks[0].key,
        )

    def test_patch_post_execution_webhook_unauthenticated(self, url, api_client):
        resp = api_client.patch(url)
        assert resp.status_code == 401

    def test_patch_post_execution_webhook_wrong_scope(
        self, url, api_client, generate_auth_header
    ):
        auth_header = generate_auth_header(scopes=[WEBHOOK_READ])
        resp = api_client.patch(
            url,
            headers=auth_header,
        )
        assert resp.status_code == 403

    def test_update_name_and_order_and_direction(
        self,
        db,
        generate_auth_header,
        api_client,
        url,
        policy_pre_execution_webhooks,
        https_connection_config,
    ):
        webhook = PolicyPostWebhook.filter(
            db=db, conditions=(PolicyPostWebhook.key == "cache_busting_webhook")
        ).first()
        db.refresh(webhook)
        assert webhook.order == 0
        request_body = {
            "name": "Better Webhook Name",
            "order": 1,
            "direction": "two_way",
        }
        auth_header = generate_auth_header(scopes=[WEBHOOK_CREATE_OR_UPDATE])
        resp = api_client.patch(url, headers=auth_header, json=request_body)
        assert resp.status_code == 200
        response_body = json.loads(resp.text)
        assert response_body == {
            "resource": {
                "direction": "two_way",
                "key": "cache_busting_webhook",
                "name": "Better Webhook Name",
                "connection_config": {
                    "name": https_connection_config.name,
                    "key": "my_webhook_config",
                    "connection_type": "https",
                    "access": "read",
                    "created_at": stringify_date(https_connection_config.created_at),
                    "updated_at": stringify_date(https_connection_config.updated_at),
                    "last_test_timestamp": None,
                    "last_test_succeeded": None,
                },
                "order": 1,
            },
            "reordered": [
                {"key": "cleanup_webhook", "order": 0},
                {"key": "cache_busting_webhook", "order": 1},
            ],
        }

        db.refresh(webhook)
        assert webhook.order == 1
