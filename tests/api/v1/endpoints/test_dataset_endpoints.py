import json
from typing import Dict, List, Optional
from unittest import mock
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi_pagination import Params
from starlette.testclient import TestClient
from sqlalchemy.orm import Session
import pytest

from fidesops.models.datasetconfig import DatasetConfig
from fidesops.models.connectionconfig import ConnectionConfig
from fidesops.api.v1.scope_registry import (
    DATASET_CREATE_OR_UPDATE,
    DATASET_READ,
    DATASET_DELETE,
)
from fidesops.api.v1.urn_registry import (
    DATASET_VALIDATE,
    DATASETS,
    DATASET_BY_KEY,
    V1_URL_PREFIX,
)


def _reject_key(dict: Dict, key: str) -> Dict:
    """Return a copy of the given dictionary with the given key removed"""
    result = dict.copy()
    result.pop(key, None)
    return result


def test_example_datasets(example_datasets):
    """Ensure the test fixture loads the right sample data"""
    assert example_datasets
    assert len(example_datasets) == 3
    assert example_datasets[0]["fides_key"] == "postgres_example_test_dataset"
    assert len(example_datasets[0]["collections"]) == 11
    assert example_datasets[1]["fides_key"] == "mongo_test"
    assert len(example_datasets[1]["collections"]) == 1


class TestValidateDataset:
    @pytest.fixture
    def validate_dataset_url(self, connection_config) -> str:
        path = V1_URL_PREFIX + DATASET_VALIDATE
        path_params = {"connection_key": connection_config.key}
        return path.format(**path_params)

    def test_put_validate_dataset_not_authenticated(
        self, example_datasets: List, validate_dataset_url: str, api_client
    ) -> None:
        response = api_client.put(
            validate_dataset_url, headers={}, json=example_datasets[0]
        )
        assert response.status_code == 401

    def test_put_validate_dataset_wrong_scope(
        self,
        example_datasets: List,
        validate_dataset_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_CREATE_OR_UPDATE])
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=example_datasets[0]
        )
        assert response.status_code == 403

    def test_put_validate_dataset_missing_key(
        self,
        example_datasets: List,
        validate_dataset_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        invalid_dataset = _reject_key(example_datasets[0], "fides_key")
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=invalid_dataset
        )
        assert response.status_code == 422
        details = json.loads(response.text)["detail"]
        assert ["body", "fides_key"] in [e["loc"] for e in details]

    def test_put_validate_dataset_missing_collections(
        self,
        example_datasets: List,
        validate_dataset_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        invalid_dataset = _reject_key(example_datasets[0], "collections")
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=invalid_dataset
        )
        assert response.status_code == 422
        details = json.loads(response.text)["detail"]
        assert ["body", "collections"] in [e["loc"] for e in details]

    def test_put_validate_dataset_nested_collections(
        self,
        example_datasets: List,
        validate_dataset_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        """Ensure we defensively throw an error if validating a nested collection"""

        auth_header = generate_auth_header(scopes=[DATASET_READ])
        invalid_dataset = example_datasets[0]
        invalid_dataset["collections"][0]["fields"].append(
            {
                "name": "details",
                "fields": [
                    {
                        "name": "phone",
                        "data_categories": ["user.provided.identifiable.contact"],
                    },
                    {"name": "count", "data_categories": ["system.operations"]},
                ],
            }
        )
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=invalid_dataset
        )
        assert response.status_code == 422
        details = json.loads(response.text)["detail"]
        assert ["body", "collections", 0, "fields", 6, "__root__"] in [
            e["loc"] for e in details
        ]

    def test_put_validate_dataset_invalid_length(
        self,
        example_datasets: List,
        validate_dataset_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        invalid_dataset = example_datasets[0]

        # string is properly read:
        invalid_dataset["collections"][0]["fields"][0]["fidesops_meta"] = {
            "length": 123
        }
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=invalid_dataset
        )
        assert response.status_code == 200
        assert (
            json.loads(response.text)["dataset"]["collections"][0]["fields"][0][
                "fidesops_meta"
            ]["length"]
            == 123
        )

        # fails with an invalid value
        invalid_dataset["collections"][0]["fields"][0]["fidesops_meta"] = {"length": -1}
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=invalid_dataset
        )

        assert response.status_code == 422
        assert (
            json.loads(response.text)["detail"][0]["msg"]
            == "Illegal length (-1). Only positive non-zero values are allowed."
        )

    def test_put_validate_dataset_invalid_data_type(
        self,
        example_datasets: List,
        validate_dataset_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        invalid_dataset = example_datasets[0]

        # string is properly read:
        invalid_dataset["collections"][0]["fields"][0]["fidesops_meta"] = {
            "data_type": "string"
        }
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=invalid_dataset
        )
        assert response.status_code == 200
        assert (
            json.loads(response.text)["dataset"]["collections"][0]["fields"][0][
                "fidesops_meta"
            ]["data_type"]
            == "string"
        )

        # fails with an invalid value
        invalid_dataset["collections"][0]["fields"][0]["fidesops_meta"] = {
            "data_type": "stringsssssss"
        }

        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=invalid_dataset
        )

        assert response.status_code == 422
        assert (
            json.loads(response.text)["detail"][0]["msg"]
            == "The data type stringsssssss is not supported."
        )

    def test_put_validate_dataset_invalid_fidesops_meta(
        self,
        example_datasets: List,
        validate_dataset_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        invalid_dataset = example_datasets[0]
        # Add an invalid fidesops_meta annotation to ensure our type-checking is comprehensive
        invalid_dataset["collections"][0]["fields"][0]["fidesops_meta"] = {
            "references": [
                {
                    "dataset": "postgres_example_test_dataset",
                    "field": "another.field",
                    "direction": "invalid direction!",
                },
            ]
        }
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=invalid_dataset
        )
        assert response.status_code == 422
        details = json.loads(response.text)["detail"]
        assert [
            "body",
            "collections",
            0,
            "fields",
            0,
            "fidesops_meta",
            "references",
            0,
            "direction",
        ] in [e["loc"] for e in details]

    def test_put_validate_dataset_invalid_category(
        self,
        example_datasets: List,
        validate_dataset_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        invalid_dataset = example_datasets[0].copy()
        invalid_dataset["collections"][0]["fields"][0]["data_categories"].append(
            "user.invalid.category"
        )
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=invalid_dataset
        )
        assert response.status_code == 422
        details = json.loads(response.text)["detail"]
        assert ["body", "collections", 0, "fields", 0, "data_categories"] in [
            e["loc"] for e in details
        ]

    def test_put_validate_dataset_invalid_connection_key(
        self, example_datasets: List, api_client: TestClient, generate_auth_header
    ) -> None:
        path = V1_URL_PREFIX + DATASET_VALIDATE
        path_params = {"connection_key": "nonexistent_key"}
        validate_dataset_url = path.format(**path_params)

        auth_header = generate_auth_header(scopes=[DATASET_READ])
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=example_datasets[0]
        )
        assert response.status_code == 404

    def test_put_validate_dataset_invalid_traversal(
        self,
        example_datasets: List,
        validate_dataset_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        invalid_dataset = example_datasets[0].copy()

        # Remove all the "reference" annotations; this will make traversal impossible
        for collection in invalid_dataset["collections"]:
            for field in collection["fields"]:
                if field.get("fidesops_meta"):
                    field["fidesops_meta"]["references"] = None
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=invalid_dataset
        )
        assert response.status_code == 200
        response_body = json.loads(response.text)
        assert response_body["dataset"]
        assert response_body["traversal_details"]
        assert response_body["traversal_details"]["is_traversable"] is False
        assert (
            "Some nodes were not reachable" in response_body["traversal_details"]["msg"]
        )
        assert (
            "postgres_example_test_dataset:address"
            in response_body["traversal_details"]["msg"]
        )

    def test_validate_dataset_that_references_another_dataset(
        self,
        example_datasets: List,
        validate_dataset_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        dataset = example_datasets[1]

        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=dataset
        )
        assert response.status_code == 200
        response_body = json.loads(response.text)
        assert response_body["dataset"]
        assert response_body["traversal_details"]
        assert response_body["traversal_details"]["is_traversable"] is False
        assert (
            "Referred to object postgres_example_test_dataset:customer:id does not exist"
            == response_body["traversal_details"]["msg"]
        )

    def test_put_validate_dataset(
        self,
        example_datasets: List,
        validate_dataset_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        response = api_client.put(
            validate_dataset_url, headers=auth_header, json=example_datasets[0]
        )
        assert response.status_code == 200
        response_body = json.loads(response.text)
        assert response_body["dataset"]
        assert response_body["dataset"]["fides_key"] == "postgres_example_test_dataset"
        assert response_body["traversal_details"]
        assert response_body["traversal_details"]["is_traversable"] is True
        assert response_body["traversal_details"]["msg"] is None


class TestPutDatasets:
    @pytest.fixture
    def datasets_url(self, connection_config) -> str:
        path = V1_URL_PREFIX + DATASETS
        path_params = {"connection_key": connection_config.key}
        return path.format(**path_params)

    def test_patch_datasets_not_authenticated(
        self, example_datasets: List, datasets_url, api_client
    ) -> None:
        response = api_client.patch(datasets_url, headers={}, json=example_datasets)
        assert response.status_code == 401

    def test_patch_datasets_wrong_scope(
        self,
        example_datasets: List,
        datasets_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        response = api_client.patch(
            datasets_url, headers=auth_header, json=example_datasets
        )
        assert response.status_code == 403

    def test_patch_datasets_invalid_connection_key(
        self, example_datasets: List, api_client: TestClient, generate_auth_header
    ) -> None:
        path = V1_URL_PREFIX + DATASETS
        path_params = {"connection_key": "nonexistent_key"}
        datasets_url = path.format(**path_params)

        auth_header = generate_auth_header(scopes=[DATASET_CREATE_OR_UPDATE])
        response = api_client.patch(
            datasets_url, headers=auth_header, json=example_datasets
        )
        assert response.status_code == 404

    def test_patch_datasets_bulk_create_limit_exceeded(
        self, api_client: TestClient, db: Session, generate_auth_header, datasets_url
    ):
        payload = []
        for i in range(0, 51):
            payload.append({"collections": [{"fields": [], "fides_key": i}]})

        auth_header = generate_auth_header(scopes=[DATASET_CREATE_OR_UPDATE])
        response = api_client.patch(datasets_url, headers=auth_header, json=payload)

        assert 422 == response.status_code
        assert (
            json.loads(response.text)["detail"][0]["msg"]
            == "ensure this value has at most 50 items"
        )

    def test_patch_datasets_bulk_create(
        self,
        example_datasets: List,
        datasets_url,
        api_client: TestClient,
        db: Session,
        generate_auth_header,
        connection_config,
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_CREATE_OR_UPDATE])
        response = api_client.patch(
            datasets_url, headers=auth_header, json=example_datasets
        )

        assert response.status_code == 200
        response_body = json.loads(response.text)
        assert len(response_body["succeeded"]) == 3
        assert len(response_body["failed"]) == 0

        # Confirm that the created dataset matches the values we provided
        postgres_dataset = response_body["succeeded"][0]
        postgres_config = DatasetConfig.get_by(
            db=db, field="fides_key", value="postgres_example_test_dataset"
        )
        assert postgres_config is not None
        assert postgres_dataset["fides_key"] == "postgres_example_test_dataset"
        assert postgres_dataset["name"] == "Postgres Example Test Dataset"
        assert "Example of a Postgres dataset" in postgres_dataset["description"]
        assert len(postgres_dataset["collections"]) == 11

        # Check the second dataset was created as well
        mongo_dataset = response_body["succeeded"][1]
        mongo_config = DatasetConfig.get_by(
            db=db, field="fides_key", value="mongo_test"
        )
        assert mongo_config is not None
        assert mongo_dataset["fides_key"] == "mongo_test"
        assert mongo_dataset["name"] == "Mongo Example Test Dataset"
        assert "Example of a Mongo dataset" in mongo_dataset["description"]
        assert len(mongo_dataset["collections"]) == 1

        postgres_config.delete(db)
        mongo_config.delete(db)

    def test_patch_datasets_bulk_update(
        self,
        example_datasets,
        datasets_url,
        api_client: TestClient,
        db: Session,
        generate_auth_header,
    ) -> None:
        # Create first, then update
        auth_header = generate_auth_header(scopes=[DATASET_CREATE_OR_UPDATE])
        api_client.patch(datasets_url, headers=auth_header, json=example_datasets)

        updated_datasets = example_datasets.copy()
        # Remove all collections from the postgres example, except for the customer table.
        # Note we also need to remove customer.address_id as it references the addresses table
        updated_datasets[0]["collections"] = [
            c for c in updated_datasets[0]["collections"] if c["name"] == "customer"
        ]
        updated_datasets[0]["collections"][0]["fields"] = [
            f
            for f in updated_datasets[0]["collections"][0]["fields"]
            if f["name"] != "address_id"
        ]
        # Remove the birthday field from the mongo example
        updated_datasets[1]["collections"][0]["fields"] = [
            f
            for f in updated_datasets[1]["collections"][0]["fields"]
            if f["name"] != "birthday"
        ]
        response = api_client.patch(
            datasets_url, headers=auth_header, json=updated_datasets
        )

        assert response.status_code == 200
        response_body = json.loads(response.text)
        assert len(response_body["succeeded"]) == 2
        assert len(response_body["failed"]) == 0

        postgres_dataset = response_body["succeeded"][0]
        assert postgres_dataset["fides_key"] == "postgres_example_test_dataset"
        assert (
            len(postgres_dataset["collections"]) == 1
        )  # all non-customer fields should be removed
        postgres_config = DatasetConfig.get_by(
            db=db, field="fides_key", value="postgres_example_test_dataset"
        )
        assert postgres_config is not None
        assert postgres_config.updated_at is not None

        mongo_dataset = response_body["succeeded"][1]
        assert mongo_dataset["fides_key"] == "mongo_test"
        assert "birthday" not in [
            f["name"] for f in mongo_dataset["collections"][0]["fields"]
        ]  # "birthday field should be removed
        mongo_config = DatasetConfig.get_by(
            db=db, field="fides_key", value="mongo_test"
        )
        assert mongo_config is not None
        assert mongo_config.updated_at is not None

        postgres_config.delete(db)
        mongo_config.delete(db)

    @mock.patch("fidesops.models.datasetconfig.DatasetConfig.create_or_update")
    def test_patch_datasets_failed_response(
        self,
        mock_create: Mock,
        example_datasets: List,
        datasets_url,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        mock_create.side_effect = HTTPException(mock.Mock(status=400), "Test error")
        auth_header = generate_auth_header(scopes=[DATASET_CREATE_OR_UPDATE])
        response = api_client.patch(
            datasets_url, headers=auth_header, json=example_datasets
        )
        assert response.status_code == 200  # Returns 200 regardless
        response_body = json.loads(response.text)
        assert len(response_body["succeeded"]) == 0
        assert len(response_body["failed"]) == 2

        for failed_response in response_body["failed"]:
            assert "Dataset create/update failed" in failed_response["message"]
            assert set(failed_response.keys()) == {"message", "data"}

        assert (
            response_body["failed"][0]["data"]["fides_key"]
            == example_datasets[0]["fides_key"]
        )
        assert (
            response_body["failed"][1]["data"]["fides_key"]
            == example_datasets[1]["fides_key"]
        )


class TestGetDatasets:
    @pytest.fixture
    def datasets_url(self, connection_config) -> str:
        path = V1_URL_PREFIX + DATASETS
        path_params = {"connection_key": connection_config.key}
        return path.format(**path_params)

    def test_get_datasets_not_authenticated(
        self, dataset_config, datasets_url, api_client: TestClient, generate_auth_header
    ) -> None:
        response = api_client.get(datasets_url, headers={})
        assert response.status_code == 401

    def test_get_datasets_invalid_connection_key(
        self, dataset_config, datasets_url, api_client: TestClient, generate_auth_header
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        path = V1_URL_PREFIX + DATASETS
        path_params = {"connection_key": "nonexistent_key"}
        datasets_url = path.format(**path_params)

        response = api_client.get(datasets_url, headers=auth_header)
        assert response.status_code == 404

    def test_get_datasets(
        self, dataset_config, datasets_url, api_client: TestClient, generate_auth_header
    ) -> None:
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        response = api_client.get(datasets_url, headers=auth_header)
        assert response.status_code == 200

        response_body = json.loads(response.text)
        assert len(response_body["items"]) == 1
        dataset_response = response_body["items"][0]
        assert dataset_response["fides_key"] == "postgres_example_subscriptions_dataset"
        assert len(dataset_response["collections"]) == 1

        assert response_body["total"] == 1
        assert response_body["page"] == 1
        assert response_body["size"] == Params().size


def get_dataset_url(
    connection_config: Optional[ConnectionConfig] = None,
    dataset_config: Optional[DatasetConfig] = None,
) -> str:
    """Helper to construct the DATASET_BY_KEY URL, substituting valid/invalid keys in the path"""
    path = V1_URL_PREFIX + DATASET_BY_KEY
    connection_key = "nonexistent_key"
    if connection_config:
        connection_key = connection_config.key
    fides_key = "nonexistent_key"
    if dataset_config:
        fides_key = dataset_config.fides_key
    path_params = {"connection_key": connection_key, "fides_key": fides_key}
    return path.format(**path_params)


class TestGetDataset:
    def test_get_dataset_not_authenticated(
        self, dataset_config, connection_config, api_client
    ) -> None:
        dataset_url = get_dataset_url(connection_config, dataset_config)
        response = api_client.get(dataset_url, headers={})
        assert response.status_code == 401

    def test_get_dataset_wrong_scope(
        self,
        dataset_config,
        connection_config,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        dataset_url = get_dataset_url(connection_config, dataset_config)
        auth_header = generate_auth_header(scopes=[DATASET_CREATE_OR_UPDATE])
        response = api_client.get(dataset_url, headers=auth_header)
        assert response.status_code == 403

    def test_get_dataset_does_not_exist(
        self,
        dataset_config,
        connection_config,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        dataset_url = get_dataset_url(connection_config, None)
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        response = api_client.get(dataset_url, headers=auth_header)
        assert response.status_code == 404

    def test_get_dataset_invalid_connection_key(
        self,
        dataset_config,
        connection_config,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        dataset_url = get_dataset_url(None, dataset_config)
        dataset_url.replace(connection_config.key, "nonexistent_key")
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        response = api_client.get(dataset_url, headers=auth_header)
        assert response.status_code == 404

    def test_get_dataset(
        self,
        dataset_config,
        connection_config,
        api_client: TestClient,
        generate_auth_header,
    ):
        dataset_url = get_dataset_url(connection_config, dataset_config)
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        response = api_client.get(dataset_url, headers=auth_header)
        assert response.status_code == 200

        response_body = json.loads(response.text)
        assert response_body["fides_key"] == dataset_config.fides_key
        assert len(response_body["collections"]) == 1


class TestDeleteDataset:
    def test_delete_dataset_not_authenticated(
        self, dataset_config, connection_config, api_client
    ) -> None:
        dataset_url = get_dataset_url(connection_config, dataset_config)
        response = api_client.delete(dataset_url, headers={})
        assert response.status_code == 401

    def test_delete_dataset_wrong_scope(
        self,
        dataset_config,
        connection_config,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        dataset_url = get_dataset_url(connection_config, dataset_config)
        auth_header = generate_auth_header(scopes=[DATASET_READ])
        response = api_client.delete(dataset_url, headers=auth_header)
        assert response.status_code == 403

    def test_delete_dataset_does_not_exist(
        self,
        dataset_config,
        connection_config,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        dataset_url = get_dataset_url(connection_config, None)
        auth_header = generate_auth_header(scopes=[DATASET_DELETE])
        response = api_client.delete(dataset_url, headers=auth_header)
        assert response.status_code == 404

    def test_delete_dataset_invalid_connection_key(
        self,
        dataset_config,
        connection_config,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        dataset_url = get_dataset_url(None, dataset_config)
        auth_header = generate_auth_header(scopes=[DATASET_DELETE])
        response = api_client.delete(dataset_url, headers=auth_header)
        assert response.status_code == 404

    def test_delete_dataset(
        self,
        db: Session,
        connection_config,
        api_client: TestClient,
        generate_auth_header,
    ) -> None:
        # Create a new dataset config so we don't run into issues trying to clean up an
        # already deleted fixture
        dataset_config = DatasetConfig.create(
            db=db,
            data={
                "connection_config_id": connection_config.id,
                "fides_key": "postgres_example_subscriptions",
                "dataset": {
                    "fides_key": "postgres_example_subscriptions",
                    "name": "Postgres Example Subscribers Dataset",
                    "description": "Example Postgres dataset created in test fixtures",
                    "dataset_type": "PostgreSQL",
                    "location": "postgres_example.test",
                    "collections": [
                        {
                            "name": "subscriptions",
                            "fields": [
                                {
                                    "name": "id",
                                    "data_categories": ["system.operations"],
                                },
                            ],
                        },
                    ],
                },
            },
        )

        dataset_url = get_dataset_url(connection_config, dataset_config)
        auth_header = generate_auth_header(scopes=[DATASET_DELETE])
        response = api_client.delete(dataset_url, headers=auth_header)
        assert response.status_code == 204

        assert (
            DatasetConfig.get_by(
                db=db, field="fides_key", value=dataset_config.fides_key
            )
            is None
        )
