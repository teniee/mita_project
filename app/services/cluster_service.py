from app.services.core.cohort.cohort_cluster_engine import CohortClusterEngine
from app.services.core.cohort.cluster_mapper import map_cluster_label


# Создаём один экземпляр кластера на всё приложение
_cluster_engine = CohortClusterEngine()


def fit_cluster_model(user_blobs: dict) -> None:
    """
    Обучает кластеризатор на входных данных пользователей.
    :param user_blobs: словарь с признаками пользователей
    """
    _cluster_engine.fit(user_blobs)


def get_user_cluster_label(user_id: str) -> str:
    """
    Возвращает текстовую метку кластера по user_id.
    :param user_id: ID пользователя
    :return: строковая метка (например, 'saver', 'spender')
    """
    label = _cluster_engine.get_label(user_id)
    return map_cluster_label(label)


def get_cluster_centroids() -> dict:
    """
    Возвращает центры всех кластеров.
    :return: словарь вида {cluster_id: {feature1: value1, ...}, ...}
    """
    return _cluster_engine.get_centroids()
