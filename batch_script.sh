#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=4 #should match the number of schemas
#SBATCH --constraint=40core
#SBATCH --mem=2GB
#SBATCH --job-name=test_job
#SBATCH --account=PAS2570
#SBATCH --output=myjob.out.%j

# Load necessary modules and environment variables
module load miniconda3
cd /fs/ess/PAS2570/smrk_proj/CSE5525_Structured_Data_Extraction
conda activate cse5525

# Execute the Python script using MPI with 4 processes matching the number of schemas
mpiexec -n 4 python generate_json_objects.py

conda deactivate