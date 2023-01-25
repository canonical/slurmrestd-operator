#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test slurmrestd charm against other SLURM charms in the latest/edge channel."""

import asyncio
import pathlib
import pytest

from helpers import (
    get_slurmctld_res,
    get_slurmd_res,
)
from pytest_operator.plugin import OpsTest
from typing import Any, Coroutine

SERIES = ["focal"]
SLURMCTLD = "slurmctld"
SLURMD = "slurmd"
SLURMDBD = "slurmdbd"
SLURMRESTD = "slurmrestd"


@pytest.mark.abort_on_fail
@pytest.mark.skip_if_deployed
@pytest.mark.parametrize("series", SERIES)
async def test_build_and_deploy(
    ops_test: OpsTest, slurmrestd_charm: Coroutine[Any, Any, pathlib.Path], series: str
    ) -> None:
    """Deploy minimal working slurmrestd charm."""
    res_slurmd = get_slurmd_res()
    res_slurmctld = get_slurmctld_res()

    charm = await slurmrestd_charm

    await asyncio.gather(
        # Fetch from charmhub slurmctld
        ops_test.model.deploy(
            SLURMCTLD,
            application_name=SLURMCTLD,
            num_units=1,
            resources=res_slurmctld,
            series=series,
        ),
        ops_test.model.deploy(
            SLURMD,
            application_name=SLURMD,
            num_units=1,
            resources=res_slurmd,
            series=series,
        ),
        ops_test.model.deploy(
            SLURMDBD,
            application_name=SLURMDBD,
            num_units=1,
            series=series,
        ),
        ops_test.model.deploy(
            charm,
            application_name=SLURMRESTD,
            num_units=1,
            series=series,
        ),
        ops_test.model.deploy(
            "percona-cluster",
            application_name="mysql",
            num_units=1,
            series="bionic",
        ),
    )
    
    # Attach ETCD resource to the slurmctld controller
    await ops_test.juju("attach-resource", SLURMCTLD, f"etcd={res_slurmctld['etcd']}")

    # Add slurmdbd relation to slurmctld
    await ops_test.model.relate(SLURMCTLD, SLURMDBD)

    # Add mysql relation to slurmdbd
    await ops_test.model.relate(SLURMDBD, "mysql")

    # Add slurmctld relation to slurmrestd
    await ops_test.model.relate(SLURMRESTD, SLURMCTLD)

    # Attach NHC resource to the slurmd controller
    await ops_test.juju("attach-resource", SLURMD, f"nhc={res_slurmd['nhc']}")

    # Add slurmctld relation to slurmd
    await ops_test.model.add_relation(SLURMD, SLURMCTLD)

    # issuing dummy update_status just to trigger an event
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=[SLURMRESTD], status="active", timeout=1000)
        assert ops_test.model.applications[SLURMRESTD].units[0].workload_status == "active"


async def test_slurmrestd_is_active(ops_test: OpsTest) -> None:
    """Test that slurmrestd is active."""
    unit = ops_test.model.applications[SLURMRESTD].units[0]
    cmd_res = (await unit.ssh(command="systemctl is-active slurmrestd")).strip("\n")
    assert cmd_res == "active"
