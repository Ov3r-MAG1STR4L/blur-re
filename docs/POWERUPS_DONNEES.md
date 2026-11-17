# Données des bonus (`pickups.bin`), résolues

Généré par `powerups_dump.py` depuis l'export JSON de `pickups.bin`. Rien d'interprété : valeurs du fichier.
Rôles d'un effet : **L** Local (vu par le joueur concerné), **E** External (vu par les autres), **I** Internal (vue intérieure), **G** Global (tout le monde). « ×n » = SpeedFactor de l'animation.

## Barge (`PickupType` #352)

- LocString 2422688926, BaseProbability 1, AIUsageType Aggressive, DoNotRandomise False
- AIPickupTypes : `[]`
- PickupSpecialFX : mesh `models\Perks\Pickups\BargePickup.model` anim `animations\Perks\BargePickup.cycle` far 350 ; Light
- PickupSpecialFXDecoy : mesh `models\Perks\Pickups\BargePickupDecoy.model` anim `animations\Perks\BargePickupDecoy.cycle` far 350 ; Light
- PickupFiringDelayFX : Post 1 s ×3 ; mesh `models/perks/BargeBuild2.model` anim `animations/perks/BargeBuild2.cycle` (not in Reflection, Cubemap) ; Camera 0.25 s ×1.5
- PickupAIFiringDelayFX : mesh `models/perks/BargeBuild2_AI.model` anim `animations/perks/BargeBuild2_AI.cycle` (not in Reflection, Cubemap)

### Barge · Normal (#780)

- BalancingData : `{"Delay": 0.2, "Health": 0.0, "Radius": 7.0, "DamageInflicted": 100, "Duration": 0.4, "MinMinePushForce": 50000.0, "MinePushForceMultiplier": 1000.0}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/perks/BargeEngulfLevel2.model` anim `animations/perks/BargeEngulfLevel2.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [VehicleToMatrix, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Barge_Rotate.model` anim `animations/perks/RoadSweeper_Barge_Rotate.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Barge_NoRotate.model` anim `animations/perks/RoadSweeper_Barge_NoRotate.cycle` (not in Reflection, Cubemap)
- **ChargingSpecialFX** [ActingCar, 0–0.95 s]
  - L : Post 1 s ×3 ; mesh `models/perks/BargeBuild2.model` anim `animations/perks/BargeBuild2.cycle` (not in Reflection, Cubemap) ; Camera 0.25 s ×1.5
  - E : mesh `models/perks/BargeBuild2_AI.model` anim `animations/perks/BargeBuild2_AI.cycle` (not in Reflection, Cubemap)
  - I : Post 1 s ; mesh `models/perks/BargeBuildBumper.model` anim `animations/perks/BargeBuildBumper.cycle` (not in Reflection, Cubemap) ; Camera 0.25 s
  - G : Light ×3
- **FiredSpecialFX** [ActingCar, 0–3 s]
  - L : Post 1 s ; Camera 2 s ; mesh `models/perks/BargeWave1LEFT.model` anim `animations/perks/BargeWave1LEFT.cycle` (not in Reflection, Cubemap)
  - E : mesh `models/perks/BargeWave1LEFT.model` anim `animations/perks/BargeWave1LEFT.cycle` (not in Reflection, Cubemap) ; Light ; mesh `models/perks/BargeWaveRing.model` anim `animations/perks/BargeWaveRing.cycle` (not in Reflection, Cubemap)
  - I : mesh `models/perks/BargeWaveBumper.model` anim `animations/perks/BargeWaveBumper.cycle` (not in Reflection, Cubemap) ; Light ; Post 1 s ; Camera 2 s
- **FiredSpecialFX** [WorldPosition, 0–2 s]
  - G : mesh `models/perks/BargeWaveResidue.model` anim `animations/perks/BargeWaveResidue.cycle` (not in Reflection, Cubemap)
- **HitVehicleSpecialFX** [TargetCar, 0–4 s]
  - G : particles `Perks_Impact_Sparks (4)` ; particles `shunted_particles_02 (4)` ; particles `Perks_Black_Bits_Small` ; mesh `models/perks/barged1.model` anim `animations/perks/barged1.cycle` (not in Reflection, Cubemap) ; particles `barged_particles_02`
- **HitVehicleSpecialFXDecoy** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/Pickups/BargePickupDecoyHit.model` anim `animations/perks/BargePickupDecoyHit.cycle` (not in Reflection, Cubemap)
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : Post 0.5 s
  - I : Post 0.5 s
  - G : mesh `models\Perks\ShieldBlockBarge1.model` anim `animations\Perks\ShieldBlockBarge1.cycle` (not in Reflection, Cubemap) ; Light
- **FiredFixedPositionSpecialFX** [WorldPosition, 0–3 s]
  - L : Post 1 s ; Camera 2 s ; mesh `models/perks/BargeWave1LEFT.model` anim `animations/perks/BargeWave1LEFT.cycle` (not in Reflection, Cubemap)
  - E : mesh `models/perks/BargeWave1LEFT.model` anim `animations/perks/BargeWave1LEFT.cycle` (not in Reflection, Cubemap) ; Light ; mesh `models/perks/BargeWaveRing.model` anim `animations/perks/BargeWaveRing.cycle` (not in Reflection, Cubemap)
  - I : mesh `models/perks/BargeWaveBumper.model` anim `animations/perks/BargeWaveBumper.cycle` (not in Reflection, Cubemap) ; Light ; Post 1 s ; Camera 2 s
- **FiredFixedPositionSpecialFX** [WorldPosition, 0–2 s]
  - G : mesh `models/perks/BargeWaveResidue.model` anim `animations/perks/BargeWaveResidue.cycle` (not in Reflection, Cubemap)
- **SplashDamageChargingSpecialFX** [ActingCar, 0–0.95 s]
  - L : Post 1 s ×3 ; Camera 0.75 s ×1.5 ; mesh `models/perks/SplashDamageBargeBuild.model` anim `animations/perks/SplashDamageBargeBuild.cycle` (not in Reflection, Cubemap)
  - E : mesh `models/perks/BargeBuild2_AI.model` anim `animations/perks/BargeBuild2_AI.cycle` (not in Reflection, Cubemap)
  - I : Post 1 s ; Camera 0.75 s ; mesh `models/perks/SplashDamageBargeBuildBumper.model` anim `animations/perks/SplashDamageBargeBuildBumper.cycle` (not in Reflection, Cubemap)
  - G : Light ×3
- **SplashDamageFiredSpecialFX** [ActingCar, 0–4 s]
  - L : Post 1 s ; Camera 2 s ; mesh `models/perks/SplashDamageBargeWave.model` anim `animations/perks/SplashDamageBargeWave.cycle` (not in Reflection, Cubemap)
  - E : mesh `models/perks/SplashDamageBargeWave.model` anim `animations/perks/SplashDamageBargeWave.cycle` (not in Reflection, Cubemap) ; Light ; mesh `models/perks/SplashDamageBargeWaveRing.model` anim `animations/perks/SplashDamageBargeWaveRing.cycle` (not in Reflection, Cubemap)
  - I : mesh `models/perks/SplashDamageBargeWaveBumper.model` anim `animations/perks/SplashDamageBargeWaveBumper.cycle` (not in Reflection, Cubemap) ; Light ; Post 1 s
- **SplashDamageFiredSpecialFX** [WorldPosition, 0–3 s]
  - G : mesh `models/perks/SplashDamageBargeWaveResidue.model` anim `animations/perks/SplashDamageBargeWaveResidue.cycle` (not in Reflection, Cubemap)
- **SafetyNetShieldedSpecialFX** [ActingCar, 0–2.5 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : mesh `models\Perks\SafetyNet_Barge.model` anim `animations\Perks\SafetyNet_Barge.cycle` (not in Reflection, Cubemap) ; Light
- **IronFistFiredSpecialFX** [ActingCar, 0–3 s]
  - L : Post 1 s ; Camera 2 s ; mesh `models/perks/BargeWave1LEFT.model` anim `animations/perks/BargeWave1LEFT.cycle` (not in Reflection, Cubemap)
  - E : mesh `models/perks/BargeWave1LEFT.model` anim `animations/perks/BargeWave1LEFT.cycle` (not in Reflection, Cubemap) ; Light ; mesh `models/perks/BargeWaveRing.model` anim `animations/perks/BargeWaveRing.cycle` (not in Reflection, Cubemap)
  - I : mesh `models/perks/BargeWaveBumper.model` anim `animations/perks/BargeWaveBumper.cycle` (not in Reflection, Cubemap) ; Light ; Post 1 s ; Camera 2 s
- **IronFistFiredSpecialFX** [WorldPosition, 0–2 s]
  - G : mesh `models/perks/BargeWaveResidue.model` anim `animations/perks/BargeWaveResidue.cycle` (not in Reflection, Cubemap)
- **LastGaspFiredSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/LastGaspSphere.model` anim `animations/perks/LastGaspSphere.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/MineBlastImplode.model` anim `animations/perks/MineBlastImplode.cycle` (not in Reflection, Cubemap)
- **SplashDamageHitVehicleSpecialFX** [TargetCar, 0–4 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : particles `Perks_Impact_Sparks (4)` ; particles `shunted_particles_02 (4)` ; particles `Perks_Black_Bits_Small` ; mesh `models/perks/barged1.model` anim `animations/perks/barged1.cycle` (not in Reflection, Cubemap) ; particles `barged_particles_02`

## Blindfire (`PickupType` #287)

- LocString 372392565, BaseProbability 1, AIUsageType Aggressive, DoNotRandomise False
- AIPickupTypes : `[{"UsageTypes": [{"WeaponDistanceAdjustment": 40.0, "WeaponAngleAdjustment": 40.0, "TriggeredByHumanOnly": false}]}, {"UsageTypes": [{"WeaponDistanceAdjustment": 30.0, "WeaponAngleAdjustment": 30.0, "TriggeredByHumanOnly": false}]}, {"UsageTypes": [{"WeaponDistanceAdjustment": 20.0, "WeaponAngleAdjustment": 20.0, "TriggeredByHumanOnly": false}]}]`
- PickupSpecialFX : Light ; mesh `models\Perks\Pickups\XPPickup.model` anim `animations\Perks\XPPickup.cycle` far 350
- PickupSpecialFXDecoy : mesh `models\Perks\Pickups\XPPickupDecoy.model` anim `animations\Perks\XPPickupDecoy.cycle` far 350 ; Light
- PickupFiringDelayFX : Post 0.5 s ; mesh `models/perks/ShuntBuild2.model` anim `animations/perks/ShuntBuild2.cycle` (not in Reflection, Cubemap) ; Camera 0.5 s ; Light
- PickupAIFiringDelayFX : mesh `models/perks/ShuntBuildAI.model` anim `animations/perks/ShuntBuildAI.cycle` (not in Reflection, Cubemap)

### Blindfire · Normal (#796)

- BalancingData : `{"Delay": 0.1, "Health": 50.0, "Radius": 0.2, "FallRate": 1.0, "HeightFromGround": 0.3, "Speed": 300.0, "DamageInflicted": 50, "WarningDistance": 100.0, "WarningDot": 0.99}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/perks/Blindfire_Engulf_Car.model` anim `animations/perks/Blindfire_Engulf_Car.cycle`
- **RoadsweeperedSpecialFX** [VehicleToMatrix, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Bolt_Rotate.model` anim `animations/perks/RoadSweeper_Bolt_Rotate.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Bolt_NoRotate.model` anim `animations/perks/RoadSweeper_Bolt_NoRotate.cycle` (not in Reflection, Cubemap)
- **ChargingSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/Blind_build_01.model` anim `animations/perks/Blind_build_01.cycle` (not in Reflection, Cubemap) ×2
- **FiredSpecialFX** [ActingCar, 0–1 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : Light
- **HitVehicleSpecialFX** [TargetCar, 0–2 s]
  - E : Light ; Light
  - G : particles `Perks_Impact_Sparks (4)` ; particles `bolted_particles_01` ; mesh `models/perks/Blindfire_hit_01.model` anim `animations/perks/Blindfire_hit_01.cycle` (not in Reflection, Cubemap) ×3 ; particles `Perks_Black_Bits_Small` ; Light ; mesh `models/perks/Blindfire_Pow_01.model` anim `animations/perks/Blindfire_Pow_01.cycle` (not in Reflection, Cubemap) ×2
- **HitVehicleSpecialFXDecoy** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/Pickups/XPPickupDecoyHit.model` anim `animations/perks/XPPickupDecoyHit.cycle` (not in Reflection, Cubemap)
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : Post 0.5 s
  - I : Post 0.5 s
  - G : mesh `models\Perks\ShieldBlockBlindfire1.model` anim `animations\Perks\ShieldBlockBlindfire1.cycle` (not in Reflection, Cubemap) ; Light
- **ProjectileSpecialFX** [WorldPosition, 0–10 s]
  - G : mesh `models/perks/Blind_projectile_01.model` anim `animations/perks/Blind_projectile_01.cycle` (not in Reflection, Cubemap) {nœuds : E_Particles → particles `RearLightTrail (3)` ; E_Particles1 → particles `RearLightTrail (3)`} ; Light ; flare `Barge_Flare` 1 s
- **HitEnvironmentSpecialFX** [WorldPosition, 0–2 s]
  - G : particles `Perks_Impact_Sparks (4)` ; particles `bolted_particles_01` ; mesh `models/perks/Blindfire_hit_01.model` anim `animations/perks/Blindfire_hit_01.cycle` (not in Reflection, Cubemap) ×3 ; particles `Perks_Black_Bits_Small` ; Light ; mesh `models/perks/Blindfire_Pow_01.model` anim `animations/perks/Blindfire_Pow_01.cycle` (not in Reflection, Cubemap) ×2
- **SafetyNetShieldedSpecialFX** [ActingCar, 0–2.5 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : mesh `models\Perks\SafetyNet_Blindfire.model` anim `animations\Perks\SafetyNet_Blindfire.cycle` (not in Reflection, Cubemap) ; Light
- **IronFistFiredSpecialFX** [ActingCar, 0–1 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : Light

### Blindfire · Reversed (#683)

- BalancingData : `{"Delay": 0.1, "Health": 50.0, "Radius": 0.2, "FallRate": 0.7, "HeightFromGround": 0.3, "Speed": 50.0, "DamageInflicted": 50, "WarningDistance": 100.0, "WarningDot": 0.99}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/perks/Blindfire_Engulf_Car.model` anim `animations/perks/Blindfire_Engulf_Car.cycle`
- **ChargingSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/Blindfire_build_rev.model` anim `animations/perks/Blindfire_build_rev.cycle` (not in Reflection, Cubemap) ×8
- **FiredSpecialFX** [ActingCar, 0–1 s]
  - L : Post 1 s
  - E : Light
  - I : Post 1 s
- **HitVehicleSpecialFX** [TargetCar, 0–2 s]
  - E : Light ; Light
  - G : particles `Perks_Impact_Sparks (4)` ; particles `bolted_particles_01` ; mesh `models/perks/Blindfire_hit_01.model` anim `animations/perks/Blindfire_hit_01.cycle` (not in Reflection, Cubemap) ×3 ; particles `Perks_Black_Bits_Small` ; Light ; mesh `models/perks/Blindfire_Pow_01.model` anim `animations/perks/Blindfire_Pow_01.cycle` (not in Reflection, Cubemap) ×2
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : Post 0.5 s
  - I : Post 0.5 s
  - G : mesh `models\Perks\ShieldBlockBlindfire1.model` anim `animations\Perks\ShieldBlockBlindfire1.cycle` (not in Reflection, Cubemap) ; Light
- **ProjectileSpecialFX** [WorldPosition, 0–10 s]
  - G : mesh `models/perks/Blind_projectile_01.model` anim `animations/perks/Blind_projectile_01.cycle` (not in Reflection, Cubemap) ; Light ; flare `Barge_Flare` 1 s
- **HitEnvironmentSpecialFX** [WorldPosition, 0–2 s]
  - G : particles `Perks_Impact_Sparks (4)` ; particles `bolted_particles_01` ; mesh `models/perks/Blindfire_hit_01.model` anim `animations/perks/Blindfire_hit_01.cycle` (not in Reflection, Cubemap) ×3 ; particles `Perks_Black_Bits_Small` ; Light ; mesh `models/perks/Blindfire_Pow_01.model` anim `animations/perks/Blindfire_Pow_01.cycle` (not in Reflection, Cubemap) ×2
- **SafetyNetShieldedSpecialFX** [ActingCar, 0–2.5 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : mesh `models\Perks\SafetyNet_Blindfire.model` anim `animations\Perks\SafetyNet_Blindfire.cycle` (not in Reflection, Cubemap) ; Light
- **IronFistFiredSpecialFX** [ActingCar, 0–1 s]
  - L : Post 1 s
  - E : Light
  - I : Post 1 s

### Blindfire · Modified (#191)

- BalancingData : `{"Delay": 0.1, "Health": 50.0, "Radius": 0.4, "FallRate": 0.0, "HeightFromGround": 0.3, "Speed": 300.0, "DamageInflicted": 50, "WarningDistance": 100.0, "WarningDot": 0.99}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/perks/Blindfire_Engulf_Car.model` anim `animations/perks/Blindfire_Engulf_Car.cycle`
- **ChargingSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/BlindfireShotgunBuild.model` anim `animations/perks/BlindfireShotgunBuild.cycle` (not in Reflection, Cubemap) ×2
- **FiredSpecialFX** [ActingCar, 0–1 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : Light
- **HitVehicleSpecialFX** [TargetCar, 0–2 s]
  - E : Light ; Light
  - G : particles `Perks_Impact_Sparks (4)` ; particles `shunted_particles_02 (8)` ; mesh `models/perks/Blindfire_hit_01.model` anim `animations/perks/Blindfire_hit_01.cycle` (not in Reflection, Cubemap) ×3 ; particles `Perks_Black_Bits_Small` ; particles `shunted_particles_02 (5)` ; Light ; mesh `models/perks/BlindfireShotgunPow.model` anim `animations/perks/BlindfireShotgunPow.cycle` (not in Reflection, Cubemap) ×2
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : Post 0.5 s
  - I : Post 0.5 s
  - G : mesh `models\Perks\ShieldBlockBlindfire1.model` anim `animations\Perks\ShieldBlockBlindfire1.cycle` (not in Reflection, Cubemap) ; Light
- **ProjectileSpecialFX** [WorldPosition, 0–10 s]
  - G : mesh `models/perks/Bolt_Shotgun_Projectile.model` anim `animations/perks/Bolt_Shotgun_Projectile.cycle` (not in Reflection, Cubemap) ; Light ; flare `Barge_Flare` 1 s
- **HitEnvironmentSpecialFX** [WorldPosition, 0–2 s]
  - G : particles `Perks_Impact_Sparks (4)` ; particles `shunted_particles_02 (8)` ; mesh `models/perks/Blindfire_hit_01.model` anim `animations/perks/Blindfire_hit_01.cycle` (not in Reflection, Cubemap) ×3 ; particles `Perks_Black_Bits_Small` ; particles `shunted_particles_02 (5)` ; Light ; mesh `models/perks/BlindfireShotgunPow.model` anim `animations/perks/BlindfireShotgunPow.cycle` (not in Reflection, Cubemap) ×2
- **SafetyNetShieldedSpecialFX** [ActingCar, 0–2.5 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : mesh `models\Perks\SafetyNet_Blindfire.model` anim `animations\Perks\SafetyNet_Blindfire.cycle` (not in Reflection, Cubemap) ; Light
- **IronFistFiredSpecialFX** [ActingCar, 0–1 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : Light

### Blindfire · ReversedModified (#559)

- BalancingData : `{"Delay": 0.1, "Health": 50.0, "Radius": 0.2, "FallRate": 0.7, "HeightFromGround": 0.3, "Speed": 50.0, "DamageInflicted": 50, "WarningDistance": 100.0, "WarningDot": 0.99}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/perks/Blindfire_Engulf_Car.model` anim `animations/perks/Blindfire_Engulf_Car.cycle`
- **ChargingSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/BlindfireShotgunBuildRev.model` anim `animations/perks/BlindfireShotgunBuildRev.cycle` (not in Reflection, Cubemap) ×2
- **FiredSpecialFX** [ActingCar, 0–1 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : Light
- **HitVehicleSpecialFX** [TargetCar, 0–2 s]
  - E : Light ; Light
  - G : particles `Perks_Impact_Sparks (4)` ; particles `shunted_particles_02 (8)` ; mesh `models/perks/Blindfire_hit_01.model` anim `animations/perks/Blindfire_hit_01.cycle` (not in Reflection, Cubemap) ×3 ; particles `Perks_Black_Bits_Small` ; particles `shunted_particles_02 (5)` ; Light ; mesh `models/perks/BlindfireShotgunPow.model` anim `animations/perks/BlindfireShotgunPow.cycle` (not in Reflection, Cubemap) ×2
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : Post 0.5 s
  - I : Post 0.5 s
  - G : mesh `models\Perks\ShieldBlockBlindfire1.model` anim `animations\Perks\ShieldBlockBlindfire1.cycle` (not in Reflection, Cubemap) ; Light
- **ProjectileSpecialFX** [WorldPosition, 0–20 s]
  - G : mesh `models/perks/Bolt_Shotgun_Projectile.model` anim `animations/perks/Bolt_Shotgun_Projectile.cycle` (not in Reflection, Cubemap) ; Light ; flare `Barge_Flare` 1 s
- **HitEnvironmentSpecialFX** [WorldPosition, 0–2 s]
  - G : particles `Perks_Impact_Sparks (4)` ; particles `shunted_particles_02 (8)` ; mesh `models/perks/Blindfire_hit_01.model` anim `animations/perks/Blindfire_hit_01.cycle` (not in Reflection, Cubemap) ×3 ; particles `Perks_Black_Bits_Small` ; particles `shunted_particles_02 (5)` ; Light ; mesh `models/perks/BlindfireShotgunPow.model` anim `animations/perks/BlindfireShotgunPow.cycle` (not in Reflection, Cubemap) ×2
- **SafetyNetShieldedSpecialFX** [ActingCar, 0–2.5 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : mesh `models\Perks\SafetyNet_Blindfire.model` anim `animations\Perks\SafetyNet_Blindfire.cycle` (not in Reflection, Cubemap) ; Light
- **IronFistFiredSpecialFX** [ActingCar, 0–1 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : Light

## Bomb (`PickupType` #155)

- LocString 955576725, BaseProbability 1, AIUsageType Aggressive, DoNotRandomise False
- AIPickupTypes : `[{"UsageTypes": []}]`
- PickupSpecialFX : mesh `models\Perks\Pickups\MinePickup.model` anim `animations\Perks\MinePickup.cycle` far 350 ; Light
- PickupSpecialFXDecoy : mesh `models\Perks\Pickups\MinePickupDecoy.model` anim `animations\Perks\MinePickupDecoy.cycle` far 350 ; Light
- PickupFiringDelayFX : mesh `models/Perks/MineEngulfLevel2.model` anim `animations/perks/MineEngulfLevel2.cycle` (not in Reflection, Cubemap)
- PickupAIFiringDelayFX : mesh `models/Perks/MineEngulfLevel2.model` anim `animations/perks/MineEngulfLevel2.cycle` (not in Reflection, Cubemap)

### Bomb · Normal (#219)

- BalancingData : `{"Delay": 0.2, "Health": 100.0, "Radius": 1.0, "OuterRadius": 3.5, "Lifespan": 60.0, "PlaceBehindDistance": 5.0, "DamageInflicted": 100, "MasterMinePrimeTimer": 0.3}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/MineEngulfLevel2.model` anim `animations/perks/MineEngulfLevel2.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [VehicleToMatrix, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Mine_Rotate.model` anim `animations/perks/RoadSweeper_Mine_Rotate.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Mine_NoRotate.model` anim `animations/perks/RoadSweeper_Mine_NoRotate.cycle` (not in Reflection, Cubemap)
- **ChargingSpecialFX** [ActingCar, 0–0.3 s]
  - L : Post 0.3 s
  - I : Post 0.3 s
  - G : mesh `models/perks/MineBuild1.model` anim `animations/perks/MineBuild1.cycle` (not in Reflection, Cubemap)
- **FiredSpecialFX** [ActingCar, 0–1 s]
  - L : Post 0.5 s
- **HitVehicleSpecialFX** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - E : particles `Perks_Black_Bits_Small`
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/mined1.model` anim `animations/perks/mined1.cycle` (not in Reflection, Cubemap)
- **HitVehicleSpecialFXDecoy** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/Pickups/MinePickupDecoyHit.model` anim `animations/perks/MinePickupDecoyHit.cycle` (not in Reflection, Cubemap)
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
  - I : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
  - G : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
- **MineSpecialFX** [WorldPosition, 0–0.4166 s]
  - G : Light ; flare `Yellow Light` 20 s ; mesh `models/perks/MineCore1.model` anim `animations/perks/MineCore1.cycle` (not in Reflection, Cubemap) ; particles `mine_particles (2)` ; mesh `models/perks/MineCore2.model` anim `animations/perks/MineCore2.cycle` (not in Reflection, Cubemap)
- **ExplodeSpecialFX** [WorldPosition, 0–3 s]
  - E : mesh `models/perks/MineBallExpand.model` anim `animations/perks/MineBallExpand.cycle` (not in Reflection, Cubemap)
  - G : flare `Yellow Light` 0.5 s ; Light ; mesh `models/perks/MineBoomCircles.model` anim `animations/perks/MineBoomCircles.cycle` (not in Reflection, Cubemap) ; particles `mine_particles` ; mesh `models/perks/MineBlastResidue.model` anim `animations/perks/MineBlastResidue.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/MineBlastImplode.model` anim `animations/perks/MineBlastImplode.cycle` (not in Reflection, Cubemap) ×1.2
- **SafetyNetShieldedSpecialFX** [ActingCar, 0–2.5 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : mesh `models\Perks\SafetyNet_Mine.model` anim `animations\Perks\SafetyNet_Mine.cycle` (not in Reflection, Cubemap) ; Light
- **IronFistFiredSpecialFX** [ActingCar, 0–1 s]
  - L : Post 0.5 s
- **MasterMinePrimedSpecialFX** [VehicleToMatrix, 0–1 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : mesh `models/perks/MasterMine01.model` anim `animations/perks/MasterMine01.cycle` (not in Reflection, Cubemap) ; Light ; particles `shunted_particles_02 (3)`
- **MasterMineEquipedSpecialFX** [WorldPosition, 0–0.4166 s]
  - G : Light ; flare `Yellow Light` 20 s ; mesh `models/perks/MasterMineCore1.model` anim `animations/perks/MasterMineCore1.cycle` (not in Reflection, Cubemap) ; particles `mine_particles (2)` ; mesh `models/perks/MineCore2.model` anim `animations/perks/MineCore2.cycle` (not in Reflection, Cubemap)

### Bomb · DoubleTap (#702)

- BalancingData : `{"Delay": 0.3, "Health": 100.0, "Radius": 2.0, "OuterRadius": 5.0, "Lifespan": 3.0, "PlaceBehindDistance": 5.0, "DamageInflicted": 100, "MasterMinePrimeTimer": 0.0}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/MineEngulfLevel2.model` anim `animations/perks/MineEngulfLevel2.cycle` (not in Reflection, Cubemap)
- **ChargingSpecialFX** [ActingCar, 0–0.3 s]
  - L : Post 0.3 s
  - I : Post 0.3 s
  - G : mesh `models/perks/MineBuild1.model` anim `animations/perks/MineBuild1.cycle` (not in Reflection, Cubemap)
- **HitVehicleSpecialFX** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - E : particles `Perks_Black_Bits_Small`
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/mined1.model` anim `animations/perks/mined1.cycle` (not in Reflection, Cubemap)
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
  - I : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
  - G : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
- **MineSpecialFX** [WorldPosition, 0–0.4166 s]
  - G : Light ; flare `Yellow Light` 20 s ; mesh `models/perks/MineCore1.model` anim `animations/perks/MineCore1.cycle` (not in Reflection, Cubemap) ; particles `mine_particles (2)` ; mesh `models/perks/MineCore2.model` anim `animations/perks/MineCore2.cycle` (not in Reflection, Cubemap)
- **ExplodeSpecialFX** [WorldPosition, 0–3 s]
  - G : mesh `models/perks/MineBallExpand.model` anim `animations/perks/MineBallExpand.cycle` (not in Reflection, Cubemap)

### Bomb · Reversed (#901)

- BalancingData : `{"Delay": 0.3, "Health": 100.0, "Radius": 0.75, "FallRate": 1.75, "MinSpeed": 250.0, "ScaledSpeed": 2.5, "Deceleration": 200.0, "HeightFromGround": 0.3, "Lifetime": 0.5, "DamageInflicted": 100, "WarningDistance": 100.0, "WarningDot": 0.9}`
- BalancingGraph : MaxBoost 0, courbe (0 ; 0.409091), (0.380319 ; 0.414773), (0.529255 ; 0)
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/MineEngulfLevel2.model` anim `animations/perks/MineEngulfLevel2.cycle` (not in Reflection, Cubemap)
- **ChargingSpecialFX** [ActingCar, 0–1 s]
  - L : Post 0.3 s
  - I : Post 0.3 s
  - G : mesh `models/perks/MineBuild1Reverse.model` anim `animations/perks/MineBuild1Reverse.cycle` (not in Reflection, Cubemap) ×0.8
- **FiredSpecialFX** [ActingCar, 0–1 s]
  - L : Post 0.5 s
- **HitVehicleSpecialFX** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - E : particles `Perks_Black_Bits_Small`
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/mined1.model` anim `animations/perks/mined1.cycle` (not in Reflection, Cubemap)
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
  - I : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
  - G : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
- **MineSpecialFX** [WorldPosition, 0–0.4166 s]
  - G : Light ; flare `Yellow Light` 20 s ; mesh `models/perks/MineCore1.model` anim `animations/perks/MineCore1.cycle` (not in Reflection, Cubemap) ; particles `mine_particles (2)` ; mesh `models/perks/MineCore2.model` anim `animations/perks/MineCore2.cycle` (not in Reflection, Cubemap)
- **ExplodeSpecialFX** [WorldPosition, 0–3 s]
  - G : mesh `models/perks/MineBallExpand.model` anim `animations/perks/MineBallExpand.cycle` (not in Reflection, Cubemap)
- **SafetyNetShieldedSpecialFX** [ActingCar, 0–2.5 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : mesh `models\Perks\SafetyNet_Mine.model` anim `animations\Perks\SafetyNet_Mine.cycle` (not in Reflection, Cubemap) ; Light

### Bomb · Mini (#495)

- BalancingData : `{"Delay": 0.3, "Health": 25.0, "Radius": 0.5, "OuterRadius": 0.0, "Lifespan": 30.0, "PlaceBehindDistance": 0.0, "DamageInflicted": 50, "MasterMinePrimeTimer": 0.0, "ThrowForceY": 1.3, "ThrowForceMin": 50000.0, "ThrowForceMax": 80000.0}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/MineEngulfLevel2.model` anim `animations/perks/MineEngulfLevel2.cycle` (not in Reflection, Cubemap)
- **ChargingSpecialFX** [ActingCar, 0–0.3 s]
  - L : Post 0.3 s
  - I : Post 0.3 s
  - G : mesh `models/perks/MineBuild1.model` anim `animations/perks/MineBuild1.cycle` (not in Reflection, Cubemap)
- **HitVehicleSpecialFX** [TargetCar, 0–3 s]
  - L : Camera 1 s ; Post 0.5 s
  - E : particles `Perks_Black_Bits_Small`
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/mined1.model` anim `animations/perks/mined1.cycle` (not in Reflection, Cubemap)
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
  - I : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
  - G : mesh `models\Perks\ShieldBlockMine1.model` anim `animations\Perks\ShieldBlockMine1.cycle` (not in Reflection, Cubemap)
- **MineSpecialFX** [WorldPosition, 0–0.4166 s]
  - G : mesh `models/perks/MineDTCore1.model` anim `animations/perks/MineDTCore1.cycle` (not in Reflection, Cubemap) ; Light ; particles `Mine_DT_01 (2)` ; particles `mine_particles (3)` ; Light
- **ExplodeSpecialFX** [WorldPosition, 0–3 s]
  - G : flare `Yellow Light` 0.5 s ; Light ; mesh `models/perks/MasterMineBoomCircles.model` anim `animations/perks/MasterMineBoomCircles.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/MasterMineBallExpand.model` anim `animations/perks/MasterMineBallExpand.cycle` (not in Reflection, Cubemap) ; particles `mine_particles` ; mesh `models/perks/MasterMineBlastResidue.model` anim `animations/perks/MasterMineBlastResidue.cycle` (not in Reflection, Cubemap)

### Bomb · Modified (#705)

- BalancingData : `{"Delay": 0.25, "Health": 1.0, "PlaceBehindDistance": 0.0, "NoMiniMinesToCreate": 5, "TotalSpreadWidth": 3}`

## Fan (`PickupType` #802)

- LocString 2063809517, BaseProbability 0, AIUsageType Passive, DoNotRandomise True
- AIPickupTypes : `[]`
- PickupSpecialFX : mesh `models\Perks\Pickups\FanPickup_Speed.model` anim `animations\Perks\Pickups\FanPickup_Speed.cycle` far 350 ; Light ; particles `Shield_Particles (8)`
- PickupSpecialFXFaded : mesh `models\Perks\Pickups\FanPickup_Speed_Dimmed.model` anim `animations\Perks\Pickups\FanPickup_Speed_Dimmed.cycle` far 350 ; Light ; particles `Shield_Particles (8)`
- PickupSpecialFXAggressive : mesh `models\Perks\Pickups\FanPickup_Aggressive.model` anim `animations\Perks\Pickups\FanPickup_Aggressive.cycle` far 350 ; Light ; particles `Shield_Particles (8)`
- PickupSpecialFXAggressiveFaded : mesh `models\Perks\Pickups\FanPickup_Aggressive_Dimmed.model` anim `animations\Perks\Pickups\FanPickup_Aggressive_Dimmed.cycle` far 350 ; Light ; particles `Shield_Particles (8)`
- PickupSpecialFXGolden : mesh `models\Perks\Pickups\FanGoldenPickup.model` anim `animations\Perks\Pickups\FanGoldenPickup.cycle` far 350 ; Light ; particles `Shield_Particles (8)`
- PickupSpecialFXGoldenFaded : mesh `models\Perks\Pickups\FanGoldenPickup_Dimmed.model` anim `animations\Perks\Pickups\FanGoldenPickup_Dimmed.cycle` far 350 ; Light

### Fan · Normal (#28)

- BalancingData : `{"Delay": 0.0, "Health": 0.0, "FansToGain": 1}`

## Nitrous (`PickupType` #502)

- LocString 477195390, BaseProbability 0.5, AIUsageType Passive, DoNotRandomise False
- AIPickupTypes : `[{"UsageTypes": []}]`
- PositionModifiers : `[{"MinPos": 1, "MaxPos": 6, "Modifier": 0.2}, {"MinPos": 7, "MaxPos": 9, "Modifier": 2.0}, {"MinPos": 10, "MaxPos": 12, "Modifier": 3.0}, {"MinPos": 13, "MaxPos": 15, "Modifier": 2.0}, {"MinPos": 16, "MaxPos": 20, "Modifier": 0.5}]`
- PickupSpecialFX : mesh `models\Perks\Pickups\NitroPickup.model` anim `animations\Perks\NitroPickup.cycle` far 350 ; Light
- PickupSpecialFXDecoy : mesh `models\Perks\Pickups\NitroPickupDecoy.model` anim `animations\Perks\NitroPickupDecoy.cycle` far 350 ; Light

### Nitrous · Normal (#628)

- BalancingData : `{"Delay": 0.0, "Health": 0.0, "Duration": 1.3, "SlowDownGraphValue": 0.5275, "DurationCheckpoint": 2.5, "SlowDownGraphValueCheckpoint": 0.45, "ClassAModifier": 1.0, "ClassBModifier": 0.95, "ClassCModifier": 0.9, "ClassDModifier": 0.85}`
- BalancingGraph : MaxBoost 500, courbe (0 ; 0.5), (0.1 ; 0.5), (0.2 ; 0.5), (0.3 ; 0.61), (0.4 ; 0.7259), (0.5 ; 0.842044), (0.6 ; 0.95151), (0.7 ; 1.04661), (0.8 ; 1.11993), (0.9 ; 1.16473), (1 ; 1.18685), (1.1 ; 1.2094), (1.2 ; 1.23238), (1.3 ; 1.2558)
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/NitroEngulfLevel2.model` anim `animations/perks/NitroEngulfLevel2.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [VehicleToMatrix, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Nitro_Rotate.model` anim `animations/perks/RoadSweeper_Nitro_Rotate.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Nitro_NoRotate.model` anim `animations/perks/RoadSweeper_Nitro_NoRotate.cycle` (not in Reflection, Cubemap)
- **HitVehicleSpecialFX** [ActingCar, 0–4 s]
  - L : Post 2 s ; Camera 4 s ; mesh `models/perks/nitrolevel2NR.model` anim `animations/perks/nitrolevel2NR.cycle` (not in Reflection, Cubemap) ×0.75 ; mesh `models/perks/nitrolevel1NR.model` anim `animations/perks/nitrolevel1NR.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/nitrolevel3NR.model` anim `animations/perks/nitrolevel3NR.cycle` (not in Reflection, Cubemap) ×0.75 ; CameraNoise 4 s
  - E : mesh `models/perks/nitrolevel2NR.model` anim `animations/perks/nitrolevel2NR.cycle` (not in Reflection, Cubemap) ×0.5 ; mesh `models/perks/nitrolevel1NR.model` anim `animations/perks/nitrolevel1NR.cycle` (not in Reflection, Cubemap) ×2 ; mesh `models/perks/nitrolevel3NR.model` anim `animations/perks/nitrolevel3NR.cycle` (not in Reflection, Cubemap) ×0.5 ; flare `Nitro Light (2)` 0.5 s
  - I : mesh `models/perks/NitroLevel3Bumper.model` anim `animations/perks/NitroLevel3Bumper.cycle` (not in Reflection, Cubemap) ; Post 2 s ; Camera 4 s
  - G : particles `shocked_sparks` ; Light
- **HitVehicleSpecialFXDecoy** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/Pickups/NitroPickupDecoyHit.model` anim `animations/perks/NitroPickupDecoyHit.cycle` (not in Reflection, Cubemap)
- **DrifterGiftedNitroSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/NitroEngulfLevel2.model` anim `animations/perks/NitroEngulfLevel2.cycle` (not in Reflection, Cubemap)

### Nitrous · DoubleTap (#393)

- BalancingData : `{"Delay": 0.0, "Health": 0.0, "LowSpeedBoost": 0.03, "DraftingBoost": 0.0001, "Duration": 2.5, "RiftTime": 2.5, "RiftRadius": 30.0, "RiftMinForce": 500.0, "RiftMaxForce": 1500.0, "RiftAngleRange": 0.1, "AirBrakeCutOff": 40.0}`
- BalancingGraph : MaxBoost 500, courbe 
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/NitroEngulfLevel2.model` anim `animations/perks/NitroEngulfLevel2.cycle` (not in Reflection, Cubemap)
- **FiredSpecialFX** [ActingCar, 0–3 s]
  - L : Post 2 s ; Camera 4 s ; CameraNoise 4 s
  - I : Post 2 s ; Camera 4 s ; CameraNoise 4 s
  - G : mesh `models/perks/Nitro_Carver.model` anim `animations/perks/Nitro_Carver.cycle` (not in Reflection, Cubemap) ; particles `shunted_particles_02 (5)` ; mesh `models/perks/nitrolevel1NR.model` anim `animations/perks/nitrolevel1NR.cycle` (not in Reflection, Cubemap) ; Light ; mesh `models/perks/Rift2.model` anim `animations/perks/Rift2.cycle` (not in Reflection, Cubemap)

### Nitrous · Reversed (#885)

- BalancingData : `{"Delay": 0.0, "Health": 0.0, "DamageInflicted": 50, "Duration": 1.2, "ForwardDot": 0.2, "RiftRangeSquared": 100.0}`
- BalancingGraph : MaxBoost 500, courbe (0 ; 1), (0.25 ; 0.5), (0.95 ; 0.5), (1 ; 0)
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/NitroEngulfLevel2.model` anim `animations/perks/NitroEngulfLevel2.cycle` (not in Reflection, Cubemap)
- **FiredSpecialFX** [ActingCar, 0–4 s]
  - L : mesh `models/perks/NitroReverse01.model` anim `animations/perks/NitroReverse01.cycle` (not in Reflection, Cubemap) ; Post 2 s ; Camera 2 s ; CameraNoise 1.75 s
  - E : mesh `models/perks/NitroReverse01.model` anim `animations/perks/NitroReverse01.cycle` (not in Reflection, Cubemap)
  - I : mesh `models/perks/NitroReverseBumper01.model` anim `animations/perks/NitroReverseBumper01.cycle` (not in Reflection, Cubemap) ; Post 2 s ; Camera 2 s
  - G : mesh `models/perks/NitroReverseBlastRings.model` anim `animations/perks/NitroReverseBlastRings.cycle` (not in Reflection, Cubemap)
- **HitVehicleSpecialFX** [TargetCar, 0–4 s]
  - L : mesh `models/perks/NitroReverse01.model` anim `animations/perks/NitroReverse01.cycle` (not in Reflection, Cubemap) ; Light
  - E : mesh `models/perks/NitroReverse01.model` anim `animations/perks/NitroReverse01.cycle` (not in Reflection, Cubemap) ; Light
  - I : mesh `models/perks/NitroReverseBumper01.model` anim `animations/perks/NitroReverseBumper01.cycle` (not in Reflection, Cubemap) ; Light
  - G : particles `shunted_particles_02 (7)`
- **ForwardSpecialFX** [ActingCar, 0–4 s]
  - L : Post 2 s ; Camera 4 s ; mesh `models/perks/nitrolevel2NR.model` anim `animations/perks/nitrolevel2NR.cycle` (not in Reflection, Cubemap) ×0.75 ; particles `shocked_sparks` ; mesh `models/perks/nitrolevel1NR.model` anim `animations/perks/nitrolevel1NR.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/nitrolevel3NR.model` anim `animations/perks/nitrolevel3NR.cycle` (not in Reflection, Cubemap) ×0.75 ; Light
  - E : mesh `models/perks/nitrolevel2.model` anim `animations/perks/nitrolevel2.cycle` (not in Reflection, Cubemap) ×0.75 ; particles `shocked_sparks` ; mesh `models/perks/nitrolevel3.model` anim `animations/perks/nitrolevel3.cycle` (not in Reflection, Cubemap) ×0.75
  - I : mesh `models/perks/NitroLevel3Bumper.model` anim `animations/perks/NitroLevel3Bumper.cycle` (not in Reflection, Cubemap) ; Post 2 s ; Camera 4 s

## Repair (`PickupType` #36)

- LocString 3215410145, BaseProbability 0.5, AIUsageType Passive, DoNotRandomise False
- AIPickupTypes : `[{"UsageTypes": [{"DamageLevel": "Wrecked"}]}, {"UsageTypes": [{"DamageLevel": "Wrecked"}]}, {"UsageTypes": [{"DamageLevel": "Wrecked"}]}]`
- PickupSpecialFX : mesh `models\Perks\Pickups\RepairPickup.model` anim `animations\Perks\RepairPickup.cycle` far 350 ; Light
- PickupSpecialFXDecoy : mesh `models\Perks\Pickups\RepairPickupDecoy.model` anim `animations\Perks\RepairPickupDecoy.cycle` far 350 ; Light

### Repair · Normal (#647)

- BalancingData : `{"Delay": 0.0, "Health": 0.0, "AmountToRepair": 400}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models\Perks\RepairEngulf.model` anim `animations\Perks\RepairEngulf.cycle`
- **RoadsweeperedSpecialFX** [VehicleToMatrix, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Repair_Rotate.model` anim `animations/perks/RoadSweeper_Repair_Rotate.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Repair_NoRotate.model` anim `animations/perks/RoadSweeper_Repair_NoRotate.cycle` (not in Reflection, Cubemap)
- **HitVehicleSpecialFX** [ActingCar, 0–2 s]
  - L : particles `Shield_Particles (4)` ; mesh `models\Perks\Repairing1.model` anim `animations\Perks\Repairing1.cycle` (not in Reflection, Cubemap) ; Post 2 s
  - E : mesh `models\Perks\Repairing1.model` anim `animations\Perks\Repairing1.cycle` (not in Reflection, Cubemap)
  - I : mesh `models\Perks\RepairingBumper.model` anim `animations\Perks\RepairingBumper.cycle` (not in Reflection, Cubemap) ; particles `Shield_Particles (4)` ; Post 2 s
- **HitVehicleSpecialFXDecoy** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/Pickups/RepairPickupDecoyHit.model` anim `animations/perks/RepairPickupDecoyHit.cycle` (not in Reflection, Cubemap)

## Shield (`PickupType` #399)

- LocString 3552375567, BaseProbability 0.5, AIUsageType Passive, DoNotRandomise False
- AIPickupTypes : `[]`
- PickupSpecialFX : mesh `models\Perks\Pickups\ShieldPickup.model` anim `animations\Perks\ShieldPickup.cycle` far 350 ; Light
- PickupSpecialFXDecoy : mesh `models\Perks\Pickups\ShieldPickupDecoy.model` anim `animations\Perks\ShieldPickupDecoy.cycle` far 350 ; Light

### Shield · Normal (#809)

- BalancingData : `{"Delay": 0.0, "Health": 50.0, "Lifetime": 6.0}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/shieldengulf1.model` anim `animations/perks/shieldengulf1.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [VehicleToMatrix, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Shield_Rotate.model` anim `animations/perks/RoadSweeper_Shield_Rotate.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Shield_NoRotate.model` anim `animations/perks/RoadSweeper_Shield_NoRotate.cycle` (not in Reflection, Cubemap)
- **HitVehicleSpecialFXDecoy** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/Pickups/ShieldPickupDecoyHit.model` anim `animations/perks/ShieldPickupDecoyHit.cycle` (not in Reflection, Cubemap)
- **ShieldDomeSpecialFX** [ActingCar, 0–2 s]
  - L : Post 6 s ; particles `Shield_Particles` ; mesh `models\Perks\ShieldLevel1.model` anim `animations\Perks\ShieldLevel1.cycle` (not in Reflection, Cubemap)
  - E : mesh `models\Perks\ShieldLevel1.model` anim `animations\Perks\ShieldLevel1.cycle` (not in Reflection, Cubemap)
  - I : Post 6 s ; mesh `models\Perks\ShieldLevel1Bumper.model` anim `animations\Perks\ShieldLevel1Bumper.cycle` (not in Reflection, Cubemap)
  - G : Light
- **ShieldedBoostersSpecialFX** [TargetCar, 0–2 s]
  - L : Post 2 s
  - I : Post 2 s
  - G : mesh `models\Perks\ShieldedBoosters.model` anim `animations\Perks\ShieldedBoosters.cycle` (not in Reflection, Cubemap)

### Shield · DoubleTap (#748)

- BalancingData : `{"Delay": 0.0, "Health": 50.0, "Lifetime": 12.0}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/shieldengulf1.model` anim `animations/perks/shieldengulf1.cycle` (not in Reflection, Cubemap)
- **HitVehicleSpecialFX** [ActingCar, 0–2 s]
  - L : Post 1 s ×3 ; Camera 1 s
  - I : Post 1 s ×3 ; Camera 1 s
  - G : mesh `models/perks/BatteringRamKhan.model` anim `animations/perks/BatteringRamKhan.cycle` (not in Reflection, Cubemap) {nœuds : E_ParticleSpawn → particles `Perks_Impact_Sparks` ×3} ×2 ; particles `Perks_Impact_Sparks (2)`
- **ShieldDomeSpecialFX** [ActingCar, 0–2 s]
  - L : Post 6 s ; particles `Shield_Particles` ; mesh `models\Perks\ShieldKhan1.model` anim `animations\Perks\ShieldKhan1.cycle` (not in Reflection, Cubemap)
  - E : mesh `models\Perks\ShieldKhan1.model` anim `animations\Perks\ShieldKhan1.cycle` (not in Reflection, Cubemap)
  - I : Post 6 s ; mesh `models\Perks\ShieldKhan2.model` anim `animations\Perks\ShieldKhan2.cycle` (not in Reflection, Cubemap)
  - G : Light
- **ShieldedBoostersSpecialFX** [TargetCar, 0–2 s]
  - L : Post 2 s
  - I : Post 2 s
  - G : mesh `models\Perks\ShieldedBoosters.model` anim `animations\Perks\ShieldedBoosters.cycle` (not in Reflection, Cubemap)

## Shock (`PickupType` #213)

- LocString 2560171463, BaseProbability 0.2, AIUsageType Aggressive, DoNotRandomise False
- AIPickupTypes : `[{"UsageTypes": [{"WeaponDistanceAdjustment": 50.0, "WeaponAngleAdjustment": 0.0, "TriggeredByHumanOnly": false}]}, {"UsageTypes": [{"DistanceFromPlayer": 80.0, "AngleFromPlayer": 45.0, "TriggeredByHumanOnly": false}]}, {"UsageTypes": [{"DistanceFromPlayer": 200.0, "AngleFromPlayer": 20.0, "TriggeredByHumanOnly": false}]}]`
- PickupSpecialFX : mesh `models\Perks\Pickups\ShockPickup.model` anim `animations\Perks\ShockPickup.cycle` far 350 ; Light
- PickupSpecialFXDecoy : mesh `models\Perks\Pickups\ShockPickupDecoy.model` anim `animations\Perks\ShockPickupDecoy.cycle` far 350 ; Light
- PickupFiringDelayFX : mesh `models/perks/ShockFireUp1.model` anim `animations/perks/ShockFireUp1.cycle` (not in Reflection, Cubemap) ×2 ; Post 1 s ; Camera 2 s
- PickupAIFiringDelayFX : mesh `models/Perks/shockengulf2.model` anim `animations/perks/shockengulf2.cycle` (not in Reflection, Cubemap)
- TargetteeSpecialFX : mesh `models/perks/ShockTargetDown1.model` anim `animations/perks/ShockTargetDown1.cycle` ; Light
- TargettedSpecialFX : mesh `models/perks/ShockTargetDown1.model` anim `animations/perks/ShockTargetDown1.cycle` ; Light

### Shock · Normal (#516)

- BalancingData : `{"Delay": 1.0, "Health": 0.0, "InnerRadius": 7.0, "OuterRadius": 14.0, "Lifetime": 1.5, "DamageInflicted": 100, "HeightDiff": -1.5}`
- BalancingGraph : MaxBoost 0, courbe (0 ; 0), (0.2 ; 0.2), (0.4 ; 0.25), (0.6 ; 0.4), (0.8 ; 0.5), (1 ; 0.65), (1.2 ; 0.8), (1.5 ; 0.852273)
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/shockengulf2.model` anim `animations/perks/shockengulf2.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [VehicleToMatrix, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Shock_Rotate.model` anim `animations/perks/RoadSweeper_Shock_Rotate.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Shock_NoRotate.model` anim `animations/perks/RoadSweeper_Shock_NoRotate.cycle` (not in Reflection, Cubemap)
- **ChargingSpecialFX** [ActingCar, 0–2 s]
  - L : mesh `models/perks/ShockFireUp1.model` anim `animations/perks/ShockFireUp1.cycle` (not in Reflection, Cubemap) ×2 ; Post 1 s ; Camera 2 s
  - E : mesh `models/perks/ShockFireUp1AI.model` anim `animations/perks/ShockFireUp1AI.cycle` (not in Reflection, Cubemap) ×2
  - I : mesh `models/perks/ShockFireUp1.model` anim `animations/perks/ShockFireUp1.cycle` (not in Reflection, Cubemap) ×2 ; Post 1 s
  - G : Light ; particles `shocked_sparks (2)` ; flare `Shock` 0.5 s
- **HitVehicleSpecialFX** [TargetCar, 0–4 s]
  - L : Post 1 s ; Light ; Light ; Light ; mesh `models/Perks/Shocked02.model` anim `animations/perks/Shocked02.cycle` (not in Reflection, Cubemap) ; particles `shocked_particles_02 (2)` ; Camera 1 s ; mesh `models/perks/shocksparks02.model` anim `animations/perks/shocksparks02.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/shocksparks03.model` anim `animations/perks/shocksparks03.cycle` (not in Reflection, Cubemap)
  - E : mesh `models/Perks/Shocked02.model` anim `animations/perks/Shocked02.cycle` (not in Reflection, Cubemap) ; Light ; Light ; Light ; particles `shocked_particles_02` ; mesh `models/perks/shocksparks02.model` anim `animations/perks/shocksparks02.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/shocksparks03.model` anim `animations/perks/shocksparks03.cycle` (not in Reflection, Cubemap)
- **HitVehicleSpecialFXDecoy** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/Pickups/ShockPickupDecoyHit.model` anim `animations/perks/ShockPickupDecoyHit.cycle` (not in Reflection, Cubemap)
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : Post 0.5 s
  - I : Post 0.5 s
  - G : mesh `models\Perks\ShieldBlockShock1.model` anim `animations\Perks\ShieldBlockShock1.cycle` (not in Reflection, Cubemap) ; Light
- **DomeSpecialFX** [WorldPosition, 0–1 s]
  - G : Light ; Light ; Light ; flare `Shock` 0.5 s ×1.5 ; Light ; mesh `models/perks/shocklevel2.model` anim `animations/perks/shocklevel2.cycle` ; particles `Perks_Black_Bits_Small` ; particles `Perks_Impact_Sparks (4)` ; Light ; mesh `models/perks/shocksparks02.model` anim `animations/perks/shocksparks02.cycle` (not in Reflection, Cubemap) ; Post 4 s
- **DomeSpecialFX** [WorldPosition, 0–1 s]
  - G : mesh `models/perks/ShockTargetDown1.model` anim `animations/perks/ShockTargetDown1.cycle` ; Light
- **SafetyNetShieldedSpecialFX** [ActingCar, 0–2.5 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : mesh `models\Perks\SafetyNet_Shock.model` anim `animations\Perks\SafetyNet_Shock.cycle` (not in Reflection, Cubemap) ; Light
- **IronFistDomeSpecialFX** [WorldPosition, 0–1 s]
  - G : Light ; Light ; Light ; flare `Shock` 0.5 s ×1.5 ; Light ; mesh `models/perks/shocklevel2.model` anim `animations/perks/shocklevel2.cycle` ; particles `Perks_Black_Bits_Small` ; particles `Perks_Impact_Sparks (4)` ; Light ; mesh `models/perks/shocksparks02.model` anim `animations/perks/shocksparks02.cycle` (not in Reflection, Cubemap) ; Post 4 s
- **IronFistDomeSpecialFX** [WorldPosition, 0–1 s]
  - G : mesh `models/perks/ShockTargetDown1.model` anim `animations/perks/ShockTargetDown1.cycle` ; Light

### Shock · DoubleTap (#468)

- BalancingData : `{"Delay": 1.0, "Health": 0.0, "InnerRadius": 7.0, "OuterRadius": 14.5, "Lifetime": 1.5, "DamageInflicted": 100, "HeightDiff": -1.5}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/shockengulf2.model` anim `animations/perks/shockengulf2.cycle` (not in Reflection, Cubemap)
- **ChargingSpecialFX** [ActingCar, 0–2 s]
  - L : mesh `models/perks/ShockFireUp1.model` anim `animations/perks/ShockFireUp1.cycle` (not in Reflection, Cubemap) ×2 ; Post 1 s ; Camera 2 s
  - E : mesh `models/perks/ShockFireUp1AI.model` anim `animations/perks/ShockFireUp1AI.cycle` (not in Reflection, Cubemap) ×2
  - I : mesh `models/perks/ShockFireUp1.model` anim `animations/perks/ShockFireUp1.cycle` (not in Reflection, Cubemap) ×2 ; Post 1 s
  - G : Light ; particles `shocked_sparks (2)` ; flare `Shock` 0.5 s
- **HitVehicleSpecialFX** [TargetCar, 0–3 s]
  - L : Post 1 s ; Light ; Light ; Light ; mesh `models/Perks/Shocked02.model` anim `animations/perks/Shocked02.cycle` (not in Reflection, Cubemap) ; particles `shocked_particles_02 (2)` ; Camera 1 s ; mesh `models/perks/shocksparks02.model` anim `animations/perks/shocksparks02.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/shocksparks03.model` anim `animations/perks/shocksparks03.cycle` (not in Reflection, Cubemap)
  - E : mesh `models/Perks/Shocked02.model` anim `animations/perks/Shocked02.cycle` (not in Reflection, Cubemap) ; Light ; Light ; Light ; particles `shocked_particles_02` ; mesh `models/perks/shocksparks02.model` anim `animations/perks/shocksparks02.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/shocksparks03.model` anim `animations/perks/shocksparks03.cycle` (not in Reflection, Cubemap)
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : Post 0.5 s
  - I : Post 0.5 s
  - G : mesh `models\Perks\ShieldBlockShock1.model` anim `animations\Perks\ShieldBlockShock1.cycle` (not in Reflection, Cubemap) ; Light
- **DomeSpecialFX** [WorldPosition, 0–5 s]
  - L : Light ; Light ; Light ; flare `Shock` 0.5 s ×1.5 ; Light ; mesh `models/perks/shocklevel2.model` anim `animations/perks/shocklevel2.cycle` ; particles `Perks_Black_Bits_Small` ; particles `Perks_Impact_Sparks (4)` ; Light ; mesh `models/perks/shocksparks02.model` anim `animations/perks/shocksparks02.cycle` (not in Reflection, Cubemap) ; Post 4 s
  - E : Light ; Light ; Light ; flare `Shock` 0.5 s ×1.5 ; Light ; mesh `models/perks/shocklevel2.model` anim `animations/perks/shocklevel2.cycle` ; particles `Perks_Black_Bits_Small` ; particles `Perks_Impact_Sparks (4)` ; Light ; mesh `models/perks/shocksparks02.model` anim `animations/perks/shocksparks02.cycle` (not in Reflection, Cubemap) ; Post 4 s
  - I : Light ; mesh `models/perks/shocksparks02.model` anim `animations/perks/shocksparks02.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/shocksparks03.model` anim `animations/perks/shocksparks03.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/ShockLevel2player.model` anim `animations/perks/ShockLevel2player.cycle` (not in Cubemap) ×3 ; particles `Perks_Black_Bits_Small` ; particles `Perks_Impact_Sparks (4)`
- **DomeSpecialFX** [WorldPosition, 0–3 s]
  - G : mesh `models/perks/ShockFireDown1.model` anim `animations/perks/ShockFireDown1.cycle` (not in Reflection, Cubemap) ×10

## Shunt (`PickupType` #159)

- LocString 3816108691, BaseProbability 1, AIUsageType Aggressive, DoNotRandomise False
- AIPickupTypes : `[{"UsageTypes": [{"WeaponDistanceAdjustment": 40.0, "WeaponAngleAdjustment": 40.0, "TriggeredByHumanOnly": false}]}, {"UsageTypes": [{"WeaponDistanceAdjustment": 30.0, "WeaponAngleAdjustment": 30.0, "TriggeredByHumanOnly": false}]}, {"UsageTypes": [{"WeaponDistanceAdjustment": 20.0, "WeaponAngleAdjustment": 20.0, "TriggeredByHumanOnly": false}]}]`
- PickupSpecialFX : mesh `models\Perks\Pickups\ShuntPickup.model` anim `animations\Perks\ShuntPickup.cycle` far 350 ; Light
- PickupSpecialFXDecoy : mesh `models\Perks\Pickups\ShuntPickupDecoy.model` anim `animations\Perks\ShuntPickupDecoy.cycle` far 350 ; Light
- PickupFiringDelayFX : Post 0.5 s ; mesh `models/perks/ShuntBuild2.model` anim `animations/perks/ShuntBuild2.cycle` (not in Reflection, Cubemap) ; Camera 0.5 s ; Light
- PickupAIFiringDelayFX : mesh `models/perks/ShuntBuildAI.model` anim `animations/perks/ShuntBuildAI.cycle` (not in Reflection, Cubemap)

### Shunt · Normal (#275)

- BalancingData : `{"Delay": 0.5, "Health": 100.0, "Radius": 0.75, "FallRate": 1.25, "DamageInflicted": 100, "FXDropTime": 0.2, "ShuntTurnRateScalar": 0.3, "ECMActivationDist": 13.0, "ECMDeactivationDist": 20.0, "ECMWarningDist": 25.0, "ECMWarningEnabled": true}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/perks/Shunt_Flow_Car_02.model` anim `animations/perks/Shunt_Flow_Car_02.cycle`
- **RoadsweeperedSpecialFX** [VehicleToMatrix, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Shunt_Rotate.model` anim `animations/perks/RoadSweeper_Shunt_Rotate.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Shunt_NoRotate.model` anim `animations/perks/RoadSweeper_Shunt_NoRotate.cycle` (not in Reflection, Cubemap)
- **ChargingSpecialFX** [ActingCar, 0–0.5 s]
  - L : Post 0.5 s ; mesh `models/perks/ShuntBuild2.model` anim `animations/perks/ShuntBuild2.cycle` (not in Reflection, Cubemap) ; Camera 0.5 s ; Light
  - E : mesh `models/perks/ShuntBuildAI.model` anim `animations/perks/ShuntBuildAI.cycle` (not in Reflection, Cubemap)
  - I : Post 0.5 s ; mesh `models/perks/ShuntBuild2Bumper.model` anim `animations/perks/ShuntBuild2Bumper.cycle` (not in Reflection, Cubemap) ; Camera 0.5 s
- **FiredSpecialFX** [GroundIcon, 0–5 s]
  - L : Camera 1 s ×4 ; Post 0.5 s ; CameraNoise 1 s
  - G : mesh `models/perks/shuntlevel1.model` anim `animations/perks/shuntlevel1.cycle` (not in Reflection, Cubemap) ×0.25
- **HitVehicleSpecialFX** [TargetCar, 0–4 s]
  - L : Post 0.5 s ; Camera 1 s
  - E : Light ; particles `shunted_particles_02` ; mesh `models/perks/ShuntPow1.model` anim `animations/perks/ShuntPow1.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/ShuntHit1.model` anim `animations/perks/ShuntHit1.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/ShuntPow2.model` anim `animations/perks/ShuntPow2.cycle` (not in Reflection, Cubemap) ×0.25
  - I : Post 0.5 s ; Camera 1 s
  - G : particles `Perks_Impact_Sparks (4)` ; particles `shunted_particles_02 (8)` ; mesh `models/perks/Shunted1.model` anim `animations/perks/Shunted1.cycle` (not in Reflection, Cubemap) ; particles `Perks_Black_Bits_Small` ; particles `shunted_particles_02 (5)` ; Light ; Light ; Light
- **HitVehicleSpecialFXDecoy** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/Pickups/ShuntPickupDecoyHit.model` anim `animations/perks/ShuntPickupDecoyHit.cycle` (not in Reflection, Cubemap)
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : Post 0.5 s
  - I : Post 0.5 s
  - G : mesh `models\Perks\ShieldBlockShunt1.model` anim `animations\Perks\ShieldBlockShunt1.cycle` (not in Reflection, Cubemap) ; Light
- **ProjectileSpecialFX** [WorldPosition, 0–0.208333 s]
  - G : mesh `models/perks/ShuntProjectile1.model` anim `animations/perks/ShuntProjectile1.cycle` (not in Reflection, Cubemap) ; Light ; particles `Shield_Particles (2)` ; flare `Red_Flare` 1 s
- **ProjectileDroppedSpecialFX** [WorldPosition, 0–2 s]
  - G : mesh `models/perks/ShuntRing1.model` anim `animations/perks/ShuntRing1.cycle` (not in Reflection, Cubemap)
- **HitEnvironmentSpecialFX** [WorldPosition, 0–3 s]
  - G : particles `Perks_Impact_Sparks (4)` ; particles `shunted_particles_02 (8)` ; particles `Perks_Black_Bits_Small` ; Light ; particles `shunted_particles_02` ; mesh `models/perks/ShuntPow1.model` anim `animations/perks/ShuntPow1.cycle` (not in Reflection, Cubemap) ×2 ; mesh `models/perks/ShuntHit1.model` anim `animations/perks/ShuntHit1.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/ShuntPow2.model` anim `animations/perks/ShuntPow2.cycle` (not in Reflection, Cubemap) ; particles `shunted_particles_02 (5)` ; mesh `models/perks/ShuntedBall1.model` anim `animations/perks/ShuntedBall1.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/ShuntRing1.model` anim `animations/perks/ShuntRing1.cycle` (not in Reflection, Cubemap)
- **ExplodeSpecialFX** [WorldPosition, 0–1 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : ParticleSpecialFX dynamiceffects/ParticleSpecialFX/#891 ; Light
- **ExplodeSpecialFX** [WorldPosition, 0–3 s]
  - G : particles `Perks_Impact_Sparks (4)` ; particles `shunted_particles_02 (8)` ; particles `Perks_Black_Bits_Small` ; Light ; particles `shunted_particles_02` ; mesh `models/perks/ShuntPow1.model` anim `animations/perks/ShuntPow1.cycle` (not in Reflection, Cubemap) ×2 ; mesh `models/perks/ShuntHit1.model` anim `animations/perks/ShuntHit1.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/ShuntPow2.model` anim `animations/perks/ShuntPow2.cycle` (not in Reflection, Cubemap) ; particles `shunted_particles_02 (5)` ; mesh `models/perks/ShuntedBall1.model` anim `animations/perks/ShuntedBall1.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/ShuntRing1.model` anim `animations/perks/ShuntRing1.cycle` (not in Reflection, Cubemap)
- **SafetyNetShieldedSpecialFX** [ActingCar, 0–2.5 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : mesh `models\Perks\SafetyNet_Shunt.model` anim `animations\Perks\SafetyNet_Shunt.cycle` (not in Reflection, Cubemap) ; Light
- **IronFistFiredSpecialFX** [GroundIcon, 0–5 s]
  - L : Camera 1 s ×4 ; Post 0.5 s ; CameraNoise 1 s
  - G : mesh `models/perks/shuntlevel1.model` anim `animations/perks/shuntlevel1.cycle` (not in Reflection, Cubemap) ×0.25

### Shunt · DoubleTap (#34)

- BalancingData : `{"Delay": 0.5, "Health": 100.0, "ShotDelay": 0.5}`
- **ChargingSpecialFX** [ActingCar, 0–1 s]
  - L : Post 0.5 s ; mesh `models/perks/ShuntBuild2.model` anim `animations/perks/ShuntBuild2.cycle` (not in Reflection, Cubemap) ; Camera 0.5 s ; Light
  - E : mesh `models/perks/ShuntBuildAI.model` anim `animations/perks/ShuntBuildAI.cycle` (not in Reflection, Cubemap)
  - I : Post 0.5 s ; mesh `models/perks/ShuntBuild2Bumper.model` anim `animations/perks/ShuntBuild2Bumper.cycle` (not in Reflection, Cubemap) ; Camera 0.5 s
- **FiredSpecialFX** [GroundIcon, 0–5 s]
  - L : Camera 1 s ×4 ; Post 0.5 s ; CameraNoise 1 s
  - G : mesh `models/perks/shuntlevel1.model` anim `animations/perks/shuntlevel1.cycle` (not in Reflection, Cubemap) ×0.25

### Shunt · Reversed (#704)

- BalancingData : `{"Delay": 0.2, "Health": 100.0, "Radius": 0.75, "FallRate": 1.5, "DamageInflicted": 100, "FXDropTime": 0.2, "Speed": 50.0, "HeightFromGround": 0.2, "WarningDistance": 70.0, "WarningDot": 0.9}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/perks/Shunt_Flow_Car_02.model` anim `animations/perks/Shunt_Flow_Car_02.cycle`
- **ChargingSpecialFX** [ActingCar, 0–1 s]
  - L : Post 0.5 s ; mesh `models/perks/ShuntBuildRev.model` anim `animations/perks/ShuntBuildRev.cycle` (not in Reflection, Cubemap) ×4.375 ; Camera 0.5 s ; Light
  - E : mesh `models/perks/ShuntBuildAI.model` anim `animations/perks/ShuntBuildAI.cycle` (not in Reflection, Cubemap)
  - I : Post 0.5 s ×2.5 ; Camera 0.5 s ×2.5
- **FiredSpecialFX** [ActingCar, 0–5 s]
  - L : Camera 1 s ×4 ; Post 0.5 s ; CameraNoise 1 s
  - I : Camera 1 s ×4 ; Post 0.5 s ; CameraNoise 1 s
- **HitVehicleSpecialFX** [TargetCar, 0–4 s]
  - L : Post 0.5 s ; Camera 1 s
  - E : Light ; particles `shunted_particles_02` ; mesh `models/perks/ShuntPow1.model` anim `animations/perks/ShuntPow1.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/ShuntHit1.model` anim `animations/perks/ShuntHit1.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/ShuntPow2.model` anim `animations/perks/ShuntPow2.cycle` (not in Reflection, Cubemap) ×0.25
  - I : Post 0.5 s ; Camera 1 s
  - G : particles `Perks_Impact_Sparks (4)` ; particles `shunted_particles_02 (8)` ; mesh `models/perks/Shunted1.model` anim `animations/perks/Shunted1.cycle` (not in Reflection, Cubemap) ; particles `Perks_Black_Bits_Small` ; particles `shunted_particles_02 (5)` ; Light ; Light ; Light
- **ShieldedSpecialFX** [TargetCar, 0–1 s]
  - L : Post 0.5 s
  - I : Post 0.5 s
  - G : mesh `models\Perks\ShieldBlockShunt1.model` anim `animations\Perks\ShieldBlockShunt1.cycle` (not in Reflection, Cubemap) ; Light
- **ProjectileSpecialFX** [WorldPosition, 0–0.208333 s]
  - G : mesh `models/perks/ShuntProjectile1.model` anim `animations/perks/ShuntProjectile1.cycle` (not in Reflection, Cubemap) ; Light ; particles `Shield_Particles (2)` ; flare `Red_Flare` 1 s
- **ProjectileDroppedSpecialFX** [WorldPosition, 0–2 s]
  - G : mesh `models/perks/ShuntRing1.model` anim `animations/perks/ShuntRing1.cycle` (not in Reflection, Cubemap)
- **HitEnvironmentSpecialFX** [WorldPosition, 0–3 s]
  - G : particles `Perks_Impact_Sparks (4)` ; particles `shunted_particles_02 (8)` ; particles `Perks_Black_Bits_Small` ; Light ; particles `shunted_particles_02` ; mesh `models/perks/ShuntPow1.model` anim `animations/perks/ShuntPow1.cycle` (not in Reflection, Cubemap) ×2 ; mesh `models/perks/ShuntHit1.model` anim `animations/perks/ShuntHit1.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/ShuntPow2.model` anim `animations/perks/ShuntPow2.cycle` (not in Reflection, Cubemap) ; particles `shunted_particles_02 (5)` ; mesh `models/perks/ShuntedBall1.model` anim `animations/perks/ShuntedBall1.cycle` (not in Reflection, Cubemap) ; mesh `models/perks/ShuntRing1.model` anim `animations/perks/ShuntRing1.cycle` (not in Reflection, Cubemap)
- **SafetyNetShieldedSpecialFX** [ActingCar, 0–2.5 s]
  - L : Post 1 s
  - I : Post 1 s
  - G : mesh `models\Perks\SafetyNet_Shunt.model` anim `animations\Perks\SafetyNet_Shunt.cycle` (not in Reflection, Cubemap) ; Light
- **IronFistFiredSpecialFX** [ActingCar, 0–5 s]
  - L : Camera 1 s ×4 ; Post 0.5 s ; CameraNoise 1 s
  - I : Camera 1 s ×4 ; Post 0.5 s ; CameraNoise 1 s

## Stopwatch (`PickupType` #744)

- LocString 1823793201, BaseProbability 0, AIUsageType Aggressive, DoNotRandomise False
- AIPickupTypes : `[]`
- PickupSpecialFX : mesh `models\Perks\Pickups\StopwatchPickup.model` anim `animations\Perks\StopwatchPickup.cycle` far 350 ; Light

### Stopwatch · Normal (#389)

- BalancingData : `{"Delay": 0.0, "Health": 0.0, "TimeToGain": 0.0}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - L : mesh `models\Perks\RepairEngulf.model` anim `animations\Perks\RepairEngulf.cycle`
  - E : mesh `models\Perks\RepairEngulf.model` anim `animations\Perks\RepairEngulf.cycle`
  - I : mesh `models\Perks\RepairEngulf.model` anim `animations\Perks\RepairEngulf.cycle`
- **RoadsweeperedSpecialFX** [VehicleToMatrix, 0–1 s]
  - L : mesh `models/perks/RoadSweeper_Repair_Rotate.model` anim `animations/perks/RoadSweeper_Repair_Rotate.cycle` (not in Reflection, Cubemap)
  - E : mesh `models/perks/RoadSweeper_Repair_Rotate.model` anim `animations/perks/RoadSweeper_Repair_Rotate.cycle` (not in Reflection, Cubemap)
  - I : mesh `models/perks/RoadSweeper_Repair_Rotate.model` anim `animations/perks/RoadSweeper_Repair_Rotate.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [ActingCar, 0–1 s]
  - L : mesh `models/perks/RoadSweeper_Repair_NoRotate.model` anim `animations/perks/RoadSweeper_Repair_NoRotate.cycle` (not in Reflection, Cubemap)
  - E : mesh `models/perks/RoadSweeper_Repair_NoRotate.model` anim `animations/perks/RoadSweeper_Repair_NoRotate.cycle` (not in Reflection, Cubemap)
  - I : mesh `models/perks/RoadSweeper_Repair_NoRotate.model` anim `animations/perks/RoadSweeper_Repair_NoRotate.cycle` (not in Reflection, Cubemap)

## SuperShield (`PickupType` #652)

- LocString 21130432, BaseProbability 0, AIUsageType Passive, DoNotRandomise False
- AIPickupTypes : `[]`
- PickupSpecialFX : mesh `models\Perks\Pickups\ShieldSuperPickup.model` anim `animations\Perks\ShieldSuperPickup.cycle` far 350 ; Light
- PickupSpecialFXDecoy : mesh `models\Perks\Pickups\ShieldSuperPickupDecoy.model` anim `animations\Perks\ShieldSuperPickupDecoy.cycle` far 350 ; Light

### SuperShield · Normal (#553)

- BalancingData : `{"Delay": 0.0, "Health": 50.0, "Lifetime": 10.0, "NitroOnStartup": true, "NitroTargetSpeedInMPH": 50.0, "BoostDuringUse": true, "SteeringForwardOffset": 2.5, "SteeringBoost": 1000.0, "AccelerationBoost": 1500.0, "BrakingBoost": 1500.0, "DownForceBoost": 5000.0, "MinimumTriggerValue": 0.5, "DamagePointsOnImpact": 100, "IncreaseMassDuringUse": true, "IncreasedMass": 10000}`
- **PickedUpSpecialFX** [ActingCar, 0–2 s]
  - G : mesh `models/Perks/shieldengulf1.model` anim `animations/perks/shieldengulf1.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [VehicleToMatrix, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Shield_Rotate.model` anim `animations/perks/RoadSweeper_Shield_Rotate.cycle` (not in Reflection, Cubemap)
- **RoadsweeperedSpecialFX** [ActingCar, 0–1 s]
  - G : mesh `models/perks/RoadSweeper_Shield_NoRotate.model` anim `animations/perks/RoadSweeper_Shield_NoRotate.cycle` (not in Reflection, Cubemap)
- **HitVehicleSpecialFX** [ActingCar, 0–2 s]
  - L : Post 1 s ×3 ; Camera 1 s
  - I : Post 1 s ×3 ; Camera 1 s
  - G : mesh `models/perks/BatteringRamKhan.model` anim `animations/perks/BatteringRamKhan.cycle` (not in Reflection, Cubemap) {nœuds : E_ParticleSpawn → particles `Perks_Impact_Sparks` ×3} ×2 ; particles `Perks_Impact_Sparks (2)`
- **HitVehicleSpecialFXDecoy** [TargetCar, 0–4 s]
  - L : Camera 1 s ; Post 0.5 s
  - I : Camera 1 s ; Post 0.5 s
  - G : mesh `models/perks/Pickups/ShieldSuperPickupDecoyHit.model` anim `animations/perks/ShieldSuperPickupDecoyHit.cycle` (not in Reflection, Cubemap)
- **ShieldDomeSpecialFX** [ActingCar, 0–2 s]
  - L : Post 6 s ; mesh `models\Perks\ShieldSuper.model` anim `animations\Perks\ShieldSuper.cycle` (not in Reflection, Cubemap)
  - E : mesh `models\Perks\ShieldSuper.model` anim `animations\Perks\ShieldSuper.cycle` (not in Reflection, Cubemap)
  - I : mesh `models\Perks\ShieldSuperBumper.model` anim `animations\Perks\ShieldSuperBumper.cycle` (not in Reflection, Cubemap)
  - G : particles `Shield_Particles (2)` ; Light
- **ShieldedBoostersSpecialFX** [TargetCar, 0–2 s]
  - L : Post 2 s
  - I : Post 2 s
  - G : mesh `models\Perks\ShieldedBoosters.model` anim `animations\Perks\ShieldedBoosters.cycle` (not in Reflection, Cubemap)

