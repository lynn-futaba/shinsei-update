# app/services/services_container.py
from __future__ import annotations
import inspect
from typing import Optional

from app.config.config import RMS_IP, RMS_PORT, RMS_USER_ID, RMS_USER_KEY
from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

logger = setup_log(cfg.LOG_FOLDER, cfg.LOG_FILE, cfg.BACKUP_DAYS, logger_name="services_container")


# ======================================================================
# ServicesContainer 本体
# ======================================================================
class ServicesContainer:
    def __init__(
        self,
        *,
        wcs,
        iot_ds,
        athena,
        default_db_name: str,
        manage_service,
        lift_entrance_service,
        pallet_supply_service,
        rms_monitoring_service: Optional[object] = None,
        rms_manual_service: Optional[object] = None,
        rms_callback_service: Optional[object] = None,
        run_initialization_service=None,
        operation_rms=None,

    ):
        self.wcs = wcs
        self.iot_ds = iot_ds
        self.athena = athena
        self.default_db_name = default_db_name

        self.manage_service = manage_service
        self.lift_entrance_service = lift_entrance_service
        self.pallet_supply_service = pallet_supply_service

        self.rms_monitoring_service = rms_monitoring_service
        self.rms_manual_service = rms_manual_service
        self.rms_callback_service = rms_callback_service
        self.run_initialization_service = run_initialization_service
        self.operation_rms = operation_rms



# ======================================================================
# Safe constructor (accepts only valid kwargs)
# ======================================================================
def _construct_with_accepted_kwargs(cls, **kwargs):
    sig = inspect.signature(cls.__init__)
    accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return cls(**accepted)


# ======================================================================
#  Container Builder
# ======================================================================
def build_container(
    *,
    wcs=None,
    iot_ds=None,
    athena=None,
    default_db_name: str = "futaba_ok2_shippment",
) -> ServicesContainer:

    if wcs is None:
        raise ValueError("build_container: 'wcs' is required.")

    # --- Import (local to avoid circular dependency) ---
    from app.services.manage_service import ManageService
    from app.services.lift_entrance_service import LiftEntranceService
    from app.services.pallet_supply_service import PalletSupplyService
    from app.services.run_initialization_service import RunInitializationService
    
    from app.infrastructure.repositories.athena_repository import AthenaRepository
    from app.infrastructure.repositories.manage_repository import ManageRepository
    from app.infrastructure.repositories.worker_repository import WorkerRepository

    # ✅ Operation Flow Imports
    
    from app.infrastructure.repositories.operation_repository import OperationRepository
    from app.interfaces.api_client.post_rms_api import PostRmsApi
    from app.interfaces.api_client.operation_rms_api import OperationRMS
    


    # ==================================================================
    # Repository 初期化
    # ==================================================================
    try:
        manage_repository = _construct_with_accepted_kwargs(
            ManageRepository,
            db=wcs,
            wcs_sql=wcs,
            db_name=default_db_name,
            wcs_query=wcs,
        )
    except Exception:
        logger.exception("[services_container] Failed to init ManageRepository")
        raise

    try:
        worker_repository = _construct_with_accepted_kwargs(
            WorkerRepository,
            db=wcs,
            wcs_sql=wcs,
            wcs_query=wcs,
            db_name=default_db_name,
        )
    except Exception:
        logger.exception("[services_container] Failed to init WorkerRepository")
        raise

    try:
        athena_repository = AthenaRepository(athena)
        logger.info("[services_container] AthenaRepository initialized (REAL)")
    except Exception:
        logger.exception("[services_container] Failed to init AthenaRepository")
        raise


    try:
        operation_repository = OperationRepository(wcs, iot_ds)
        logger.info("[services_container] OperationRepository initialized")
    except Exception:
        logger.exception("[services_container] Failed to init OperationRepository")
        raise

    # ==============================================================
    # ✅ RMS API CLIENT (for OperationRMS)
    # ==============================================================
    try:
        post_rms_api = PostRmsApi(
            ip=RMS_IP,
            port=RMS_PORT,
            user_id=RMS_USER_ID,
            user_key=RMS_USER_KEY,
        )
        logger.info("[services_container] PostRmsApi initialized")
    except Exception:
        logger.exception("[services_container] Failed to init PostRmsApi")
        raise
    

    # ==================================================================
    # Service 初期化
    # ==================================================================
    manage_service = ManageService(manage_repository, athena_repository)
    lift_entrance_service = LiftEntranceService(worker_repository)
    pallet_supply_service = PalletSupplyService(worker_repository)
    
    # ==================================================================
    # RMS 関連サービス
    # ==================================================================
    # Monitoring
    rms_monitoring_service = None
    try:
        from app.services.rms_monitoring_service import RMSMonitoringService
        rms_monitoring_service = _construct_with_accepted_kwargs(
            RMSMonitoringService,
            ip=RMS_IP, port=RMS_PORT, user_id=RMS_USER_ID, user_key=RMS_USER_KEY,
            db=None, wcs_sql=wcs, athena_sql=athena, db_name=default_db_name
        )
    except Exception as ex:
        logger.error("[services_container] RMSMonitoringService not initialized: %s", ex)

    # Manual
    rms_manual_service = None
    try:
        from app.services.rms_manual_service import RMSManualService
        rms_manual_service = _construct_with_accepted_kwargs(
            RMSManualService,
            ip=RMS_IP, port=RMS_PORT, user_id=RMS_USER_ID, user_key=RMS_USER_KEY,
            db=None, wcs_sql=wcs, db_name=default_db_name,
        )
    except Exception:
        logger.exception("[services_container] Failed to init RMSManualService")

    # Callback
    rms_callback_service = None
    try:
        from app.services.rms_callback_service import RMSCallbackService
        from app.interfaces.api_client.rms_callback_api import RMSCallbackApi

        client_id = getattr(cfg, "RESPONSE", "clientid") # FTB_WCS_clientid
        version = getattr(cfg, "RMS_VERSION", "3.3.0")

        callback_api = _construct_with_accepted_kwargs(
            RMSCallbackApi,
            client_id=client_id, version=version,
            user_id=RMS_USER_ID, user_key=RMS_USER_KEY,
        )

        rms_callback_service = RMSCallbackService(
            wcs_sql=wcs,
            callback_api=callback_api,
            db_name=default_db_name,
        )
    except Exception:
        logger.exception("[services_container] Failed to init RMSCallbackService")


    # Init Service
    run_initialization_service = None
    try:
        from app.services.run_initialization_service import RunInitializationService
        run_initialization_service = _construct_with_accepted_kwargs(
            RunInitializationService,
            ip=RMS_IP, port=RMS_PORT, user_id=RMS_USER_ID, user_key=RMS_USER_KEY,
            db=None, wcs_sql=wcs, db_name=default_db_name,
        )
    except Exception:
        logger.exception("[services_container] Failed to init RunInitializationService")
        
    
                   
    # ==================================================================
    # ✅ Return Container
    # ==================================================================
    return ServicesContainer(
        wcs = wcs,
        iot_ds = iot_ds,
        athena = athena,
        default_db_name = default_db_name,

        manage_service = manage_service,
        lift_entrance_service = lift_entrance_service,
        pallet_supply_service = pallet_supply_service,

        rms_monitoring_service = rms_monitoring_service,
        rms_manual_service = rms_manual_service,
        rms_callback_service = rms_callback_service,
        run_initialization_service = run_initialization_service,

    )


__all__ = ["ServicesContainer", "build_container"]