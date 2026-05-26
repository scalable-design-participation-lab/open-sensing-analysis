from sklearn.decomposition import PCA


def pca_transform_data(
        data,
        n_components = 2,
        random_state = 42
    ):
    """
    Applies PCA to a feature table. 

    Parameters
    ----------
    data
        Feature table to transform. 
    n_components
        The number of principal components to project on (default 2).
    random_state
        Random state to pass to the PCA model. 
    """


    pca = PCA(n_components=n_components, random_state=random_state)
    transformed_data = pca.fit_transform(data)

    return transformed_data

