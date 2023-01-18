#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import pytest

from helpers import (
    fetch_slurmctld_deps,
    fetch_slurmd_deps,
)
from pytest_operator.plugin import OpsTest

ETCD = "etcd-v3.5.0-linux-amd64.tar.gz"
NHC = "lbnl-nhc-1.4.3.tar.gz"
SERIES = ["focal"]
SLURMCTLD = "slurmctld"
SLURMD = "slurmd"
SLURMDBD = "slurmdbd"
SLURMRESTD = "slurmrestd"


@pytest.mark.abort_on_fail
@pytest.mark.parametrize("series", SERIES)
@pytest.mark.skip_if_deployed
async def test_build_and_deploy(ops_test: OpsTest, series: str, slurmrestd_charm):
    """Deploy minimal working slurmrestd charm."""
    res_slurmd = fetch_slurmd_deps()
    res_slurmctld = fetch_slurmctld_deps()

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
    await ops_test.juju("attach-resource", SLURMCTLD, f"etcd={ETCD}")

    # Add slurmdbd relation to slurmctld
    await ops_test.model.relate(SLURMCTLD, SLURMDBD)

    # Add mysql relation to slurmdbd
    await ops_test.model.relate(SLURMDBD, "mysql")

    # Add slurmctld relation to slurmrestd
    await ops_test.model.relate(SLURMRESTD, SLURMCTLD)

    # Attach NHC resource to the slurmd controller
    await ops_test.juju("attach-resource", SLURMD, f"nhc={NHC}")

    # Add slurmctld relation to slurmd
    await ops_test.model.add_relation(SLURMD, SLURMCTLD)

    # issuing dummy update_status just to trigger an event
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=[SLURMRESTD], status="active", timeout=1000)
        assert ops_test.model.applications[SLURMRESTD].units[0].workload_status == "active"
