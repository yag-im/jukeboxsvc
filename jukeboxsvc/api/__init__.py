from fastapi import APIRouter

from jukeboxsvc.api.cluster import router as cluster_router
from jukeboxsvc.api.container import router as container_router
from jukeboxsvc.api.ovh_cluster import router as ovh_cluster_router

router = APIRouter()

router.include_router(container_router)
router.include_router(cluster_router)
router.include_router(ovh_cluster_router)
