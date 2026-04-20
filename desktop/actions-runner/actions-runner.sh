# Create a folder under the drive root
$ mkdir actions-runner; cd actions-runnerCopied!# Download the latest runner package
$ Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.333.1/actions-runner-win-x64-2.333.1.zip -OutFile actions-runner-win-x64-2.333.1.zipCopied!# Optional: Validate the hash
$ if((Get-FileHash -Path actions-runner-win-x64-2.333.1.zip -Algorithm SHA256).Hash.ToUpper() -ne 'd0c4fcb91f8f0754d478db5d61db533bba14cad6c4676a9b93c0b7c2a3969aa0'.ToUpper()){ throw 'Computed checksum did not match' }Copied!# Extract the installer
$ Add-Type -AssemblyName System.IO.Compression.FileSystem ; [System.IO.Compression.ZipFile]::ExtractToDirectory("$PWD/actions-runner-win-x64-2.333.1.zip", "$PWD")
Configure
# Create the runner and start the configuration experience
$ ./config.cmd --url https://github.com/nguemechieu/sopotek-quant-system --token ALTWPZIQIU3V43BSQ56FWYTJ3ZIEE# Run it!
$ ./run.cmd
