# fabric_client.py -- Hyperledger Fabric integration point for AgriChain / CropSim.
#
# CURRENT STATE: stub only (hackathon demo scope).
# The function interface is intentionally identical to what the real SDK call will use,
# so swapping in the real implementation later requires NO changes to app.py.

import logging
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)


def submit_yield_record(record: dict) -> dict:
    """
    Commit a crop-yield simulation record to the AgriChain Fabric ledger.

    Parameters
    ----------
    record : dict
        Summary payload, typically:
            crop_type           str
            predicted_yield_kg  float
            overall_stress_pct  float
            created_at          ISO-8601 str
            simulation_id       int  (off-chain DB reference)

    Returns
    -------
    dict
        Transaction receipt with status, tx_id, channel, chaincode, timestamp,
        and the original record echoed back.

    Raises
    ------
    Exception
        Any unexpected error is logged and re-raised so the caller can handle it
        safely (the caller wraps this in try/except and continues).
    """

    # ------------------------------------------------------------------
    # TODO: replace this entire stub block with the real Fabric SDK call.
    #
    # Using fabric-sdk-py (hfc):
    #
    #   from hfc.fabric import Client
    #   cli = Client(net_profile="network.json")
    #   org1_admin = cli.get_user("org1.example.com", "Admin")
    #   responses, proposal, header = await cli.chaincode_invoke(
    #       requestor=org1_admin,
    #       channel_name="agrichain-channel",
    #       peers=["peer0.org1.example.com"],
    #       args=[json.dumps(record)],
    #       cc_name="cropYieldContract",
    #       fcn="RecordYield",
    #   )
    #   tx_id = header.channel_header.tx_id
    #
    # Using the newer Fabric Gateway (recommended for Fabric 2.4+):
    #
    #   import grpc, json
    #   from grpc import ssl_channel_credentials
    #   from gateway.gateway import connect, ConnectOptions
    #
    #   channel = grpc.secure_channel("peer0.org1.example.com:7051", ssl_channel_credentials(...))
    #   gateway = connect(channel, ConnectOptions(identity=identity, signer=signer))
    #   network  = gateway.get_network("agrichain-channel")
    #   contract = network.get_contract("cropYieldContract")
    #   tx_id    = contract.submit("RecordYield", arguments=[json.dumps(record)])
    # ------------------------------------------------------------------

    # --- STUB IMPLEMENTATION ---
    # Simulates a successful on-chain write with a deterministic-looking fake tx_id.
    tx_id = "tx_" + uuid4().hex[:16]
    timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Fabric stub: simulated commit tx_id=%s for simulation_id=%s",
        tx_id, record.get("simulation_id")
    )

    return {
        "status":    "committed",
        "tx_id":     tx_id,
        "channel":   "agrichain-channel",
        "chaincode": "cropYieldContract",
        "timestamp": timestamp,
        "record":    record,
    }
