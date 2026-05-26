
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

def apply_kmeans(
        data,
        n_clusters:int = 2,
        n_runs:int = 10,
        random_state:int = 42
    ):
    """
    Applies K-means to a feature table. 

    Parameters
    ----------
    data
        feature table. 
    n_clusters
        Number of clusters (default 2).
    n_runs
        Number of times the k-means algorithm runs with distinct initial positions for the centroids. 
    random_state
        RNG seed. 

    Returns
    -------
    cluster_labels
        Cluster label of each vector. 
    centroids
        Final location of the clusters' centroids.
    score
        Silhouette score. 
    

    """

    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=n_runs)

    cluster_labels = kmeans.fit_predict(data)
    centroids = kmeans.cluster_centers_
    score=silhouette_score(data, cluster_labels)

    return cluster_labels, centroids, score



