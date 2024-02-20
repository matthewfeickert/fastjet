#!/bin/bash

reset_repository () {
    rm -rf CGAL-5.6*

    cd fastjet-core
    git reset --hard fastjet-3.4.2
    rm -rf src/ClusterSequence.cc.orig
    cd ..
}

reset_fastjet_contrib () {
    cd fastjet-contrib
    rm -rf config.log
    git reset --hard v1.014
    cd ..
}

reset_repository
# reset_fastjet_contrib

rm -rf build
python -m pip install --upgrade --verbose .

reset_repository
