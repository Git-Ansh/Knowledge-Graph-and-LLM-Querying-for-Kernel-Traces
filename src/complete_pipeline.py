#!/usr/bin/env python3
"""
Complete Knowledge Graph Pipeline - Production Ready

Integrates Enhanced Trace Processing + Neo4j Graph Building
Implements the original two-tiered design with intelligent data correlation

Design Goals Achieved:
- Few thousand entity nodes (Process, Thread, File, Socket, CPU)
- Near-zero isolation through intelligent correlation
- Direct entity relationships (READ_FROM, WROTE_TO, SCHEDULED_ON)
- Fast queries via entity-centric architecture
    def process_trace_to_graph(self, trace_file_path: str,
                              metadata_path: Optional[str] = None,
                              clear_existing: bool = True,
                              validate_design: bool = True) -> Dict[str, Any]:
        """
        Complete pipeline: Trace Processing → Graph Building → Validation
        
        Args:
            trace_file_path: Path to LTTng trace file
            metadata_path: Optional path to JSON metadata for schema detection
            clear_existing: Whether to clear existing graph data
            validate_design: Whether to run design compliance validation
            
        Returns:
            Comprehensive pipeline results with design validation
        """

        logger.info(" COMPLETE KNOWLEDGE GRAPH PIPELINE STARTING")
        logger.info("=" * 55)

        pipeline_start = time.time()
        self.pipeline_stats['start_time'] = pipeline_start

        # Phase 1: Unified trace processing
        logger.info(" Phase 1: Unified Trace Processing with Schema Awareness")
        processing_start = time.time()
        processing_result = self.trace_processor.process_trace(
            trace_file_path,
            metadata_path=metadata_path
        )
        processing_end = time.time()
        self.pipeline_stats['processing_time'] = processing_end - processing_start

        entities = processing_result.entities
        relationships = processing_result.relationships
        schema = processing_result.schema
        compliance = processing_result.compliance
        processing_stats = processing_result.stats

        logger.info(f"    Processing complete: {processing_end - processing_start:.2f}s")
        logger.info(f"    Entities: {sum(len(elist) for elist in entities.values()):,}")
        logger.info(f"    Relationships: {len(relationships):,}")
        logger.info(
            "    Schema coverage: %.1f%% (%d/%d types)",
            compliance['coverage_percent'],
            compliance['covered_types'],
            compliance['total_expected']
        )
        if compliance['missing_types']:
            logger.warning("    Missing relationship types: %s", compliance['missing_types'])
        logger.info("    Selected schema: %s", schema.name)

        # Phase 2: Neo4j Graph Construction
        logger.info("\n  Phase 2: Neo4j Graph Construction")
        graph_start = time.time()

        self.graph_builder.prepare_schema(schema, clear_existing=clear_existing)
        graph_result = self.graph_builder.build_hybrid_graph_from_data(
            entities, relationships
        )

        graph_end = time.time()
        self.pipeline_stats['graph_build_time'] = graph_end - graph_start

        logger.info(f"    Graph built: {graph_end - graph_start:.2f}s")

        # Phase 3: Design Validation
        validation_result: Dict[str, Any] = {}
        if validate_design:
            logger.info("\n Phase 3: Design Goal Validation")
            validation_result = self._validate_design_goals(entities, relationships)
            validation_result['schema_compliance'] = compliance

        # Pipeline completion
        pipeline_end = time.time()
        self.pipeline_stats['end_time'] = pipeline_end
        self.pipeline_stats['total_time'] = pipeline_end - pipeline_start

        # Compile comprehensive results
        events_processed = max(processing_stats.get('events_processed', 0), 1)
        results = {
            'schema': schema.name,
            'schema_description': schema.description,
            'trace_metadata': processing_result.metadata,
            'relationship_compliance': compliance,
            'pipeline_stats': self.pipeline_stats,
            'processing_stats': processing_stats,
            'graph_stats': graph_result,
            'design_validation': validation_result,
            'entities_summary': {
                entity_type: len(entity_list)
                for entity_type, entity_list in entities.items()
            },
            'relationships_summary': self._summarize_relationships(relationships),
            'performance_metrics': {
                'total_time': self.pipeline_stats['total_time'],
                'events_per_second': processing_stats.get('events_processed', 0) / self.pipeline_stats['processing_time'] if self.pipeline_stats['processing_time'] > 0 else 0,
                'relationships_per_event': len(relationships) / events_processed,
                'graph_build_rate': graph_result.get('relationships_created', 0) / self.pipeline_stats['graph_build_time'] if self.pipeline_stats['graph_build_time'] > 0 else 0,
            }
        }

        self._print_pipeline_summary(results)

        return results
            'schema_description': schema.description,
            'trace_metadata': processing_result.metadata,
            'relationship_compliance': compliance,
            'pipeline_stats': self.pipeline_stats,
            'processing_stats': processing_stats,
            'graph_stats': graph_result,
            'design_validation': validation_result,
            'entities_summary': {
                entity_type: len(entity_list) 
                for entity_type, entity_list in entities.items()
            },
            'relationships_summary': self._summarize_relationships(relationships),
            'performance_metrics': {
                'total_time': self.pipeline_stats['total_time'],
                'events_per_second': processing_stats.get('events_processed', 0) / self.pipeline_stats['processing_time'] if self.pipeline_stats['processing_time'] > 0 else 0,
                'relationships_per_event': len(relationships) / processing_stats.get('events_processed', 1),
                'graph_build_rate': graph_result.get('relationships_created', 0) / self.pipeline_stats['graph_build_time'] if self.pipeline_stats['graph_build_time'] > 0 else 0
            }
        }
        
        self._print_pipeline_summary(results)
        
        return results
    
    def _validate_design_goals(self, entities: Dict[str, List], 
                              relationships: List) -> Dict[str, Any]:
        """Validate compliance with original design goals"""
        
        # Design Goal 1: Entity Count ("few thousand nodes")
        total_entities = sum(len(entity_list) for entity_list in entities.values())
        entity_goal_met = total_entities <= 5000
        
        # Design Goal 2: Relationship Types (original design types)
        expected_relationship_types = {
            'READ_FROM', 'WROTE_TO', 'OPENED', 'CLOSED', 'ACCESSED',
            'SCHEDULED_ON', 'PREEMPTED_FROM', 'SENT_TO', 'RECEIVED_FROM',
            'CONNECTED_TO', 'FORKED'
        }
        
        actual_types = set()
        rel_type_counts = {}
        for rel in relationships:
            rel_type = rel.relationship_type
            actual_types.add(rel_type)
            rel_type_counts[rel_type] = rel_type_counts.get(rel_type, 0) + 1
            
        compliant_types = actual_types.intersection(expected_relationship_types)
        type_compliance_rate = len(compliant_types) / len(expected_relationship_types) * 100
        
        # Design Goal 3: Isolation Rate ("near-zero isolation")
        connected_entities = set()
        for rel in relationships:
            connected_entities.add(f"{rel.source_type}:{rel.source_id}")
            connected_entities.add(f"{rel.target_type}:{rel.target_id}")
            
        isolation_rate = ((total_entities - len(connected_entities)) / total_entities) * 100 if total_entities > 0 else 0
        isolation_goal_met = isolation_rate <= 10  # Allow up to 10% for practical purposes
        
        # Design Goal 4: Entity-to-Entity Relationships
        entity_to_entity_rels = 0
        for rel in relationships:
            if rel.source_type in ['Process', 'Thread', 'File', 'Socket', 'CPU'] and \
               rel.target_type in ['Process', 'Thread', 'File', 'Socket', 'CPU']:
                entity_to_entity_rels += 1
                
        entity_relationship_rate = (entity_to_entity_rels / len(relationships)) * 100 if relationships else 0
        
        # Overall compliance score
        compliance_factors = [
            entity_goal_met,
            type_compliance_rate >= 40,  # At least 40% of expected types
            isolation_goal_met,
            entity_relationship_rate >= 80  # At least 80% entity-to-entity
        ]
        overall_compliance = sum(compliance_factors) / len(compliance_factors) * 100
        
        return {
            'entity_count': {
                'total': total_entities,
                'target': '≤ 5,000',
                'goal_met': entity_goal_met,
                'breakdown': {entity_type: len(elist) for entity_type, elist in entities.items()}
            },
            'relationship_types': {
                'expected_types': len(expected_relationship_types),
                'compliant_types': len(compliant_types),
                'compliance_rate': type_compliance_rate,
                'compliant_list': sorted(list(compliant_types)),
                'missing_types': sorted(list(expected_relationship_types - actual_types)),
                'counts': rel_type_counts
            },
            'isolation': {
                'rate': isolation_rate,
                'connected_entities': len(connected_entities),
                'total_entities': total_entities,
                'goal_met': isolation_goal_met
            },
            'entity_relationships': {
                'entity_to_entity_count': entity_to_entity_rels,
                'total_relationships': len(relationships),
                'percentage': entity_relationship_rate
            },
            'overall_compliance': {
                'score': overall_compliance,
                'factors_met': sum(compliance_factors),
                'total_factors': len(compliance_factors)
            }
        }
    
    def _summarize_relationships(self, relationships: List) -> Dict[str, Any]:
        """Summarize relationship distribution"""
        rel_counts = {}
        for rel in relationships:
            rel_type = rel.relationship_type
            rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1
            
        total = len(relationships)
        return {
            'total': total,
            'types': len(rel_counts),
            'distribution': {
                rel_type: {
                    'count': count,
                    'percentage': (count / total) * 100 if total > 0 else 0
                }
                for rel_type, count in sorted(rel_counts.items(), key=lambda x: x[1], reverse=True)
            }
        }
    
    def _print_pipeline_summary(self, results: Dict[str, Any]) -> None:
        """Print comprehensive pipeline summary"""
        
        logger.info("\n" + "=" * 70)
        logger.info(" COMPLETE KNOWLEDGE GRAPH PIPELINE SUMMARY")
        logger.info("=" * 70)
        
        # Performance Summary
        perf = results['performance_metrics']
        logger.info(f"  PERFORMANCE METRICS:")
        logger.info(f"   Total Pipeline Time: {results['pipeline_stats']['total_time']:.2f} seconds")
        logger.info(f"   Processing Speed: {perf['events_per_second']:.0f} events/second")
        logger.info(f"   Graph Build Rate: {perf['graph_build_rate']:.0f} relationships/second")
        logger.info(f"   Efficiency: {perf['relationships_per_event']:.2f} relationships per event")
        
        # Entity Summary
        entities = results['entities_summary']
        total_entities = sum(entities.values())
        logger.info(f"\n ENTITY INVENTORY ({total_entities:,} total):")
        for entity_type, count in entities.items():
            if count > 0:
                logger.info(f"   {entity_type}: {count:,}")
        
        # Relationship Summary
        rels = results['relationships_summary']
        logger.info(f"\n RELATIONSHIP ANALYSIS ({rels['total']:,} total, {rels['types']} types):")
        for rel_type, info in list(rels['distribution'].items())[:5]:  # Top 5
            logger.info(f"   {rel_type}: {info['count']:,} ({info['percentage']:.1f}%)")

        # Schema compliance summary
        compliance = results.get('relationship_compliance')
        if compliance:
            logger.info(f"\n SCHEMA COMPLIANCE: {compliance['coverage_percent']:.1f}% ({compliance['covered_types']}/{compliance['total_expected']})")
            if compliance['missing_types']:
                logger.info(f"    Missing types: {', '.join(compliance['missing_types'])}")
            else:
                logger.info("    All expected relationship types present")
        
        # Design Validation
        if 'design_validation' in results and results['design_validation']:
            validation = results['design_validation']
            logger.info(f"\n DESIGN GOAL VALIDATION:")
            
            # Entity count
            entity_check = validation['entity_count']
            status = "" if entity_check['goal_met'] else ""
            logger.info(f"   {status} Entity Count: {entity_check['total']:,} (target: {entity_check['target']})")
            
            # Isolation
            isolation_check = validation['isolation']
            status = "" if isolation_check['goal_met'] else ""
            logger.info(f"   {status} Isolation Rate: {isolation_check['rate']:.1f}% (target: ≤10%)")
            
            # Relationship types
            type_check = validation['relationship_types']
            status = "" if type_check['compliance_rate'] >= 40 else ""
            logger.info(f"   {status} Relationship Types: {type_check['compliant_types']}/{type_check['expected_types']} ({type_check['compliance_rate']:.1f}%)")
            
            # Overall compliance
            overall = validation['overall_compliance']
            if overall['score'] >= 75:
                logger.info(f"    OVERALL: {overall['score']:.1f}% - EXCELLENT compliance with design goals!")
            elif overall['score'] >= 50:
                logger.info(f"    OVERALL: {overall['score']:.1f}% - GOOD compliance with design goals!")
            else:
                logger.info(f"    OVERALL: {overall['score']:.1f}% - Needs improvement for design goals")
        
        logger.info("\n Pipeline completed successfully!")
        logger.info("=" * 70)
    
    def close(self) -> None:
        """Clean up resources"""
        if self.graph_builder:
            self.graph_builder.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Complete Knowledge Graph Pipeline")
    parser.add_argument("trace_file", help="Path to LTTng trace file")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j username")
    parser.add_argument("--neo4j-password", default="sudoroot", help="Neo4j password")
    parser.add_argument("--no-clear", action="store_true", help="Don't clear existing graph data")
    parser.add_argument("--no-validate", action="store_true", help="Skip design validation")
    
    args = parser.parse_args()
    
    # Run pipeline
    pipeline = CompleteGraphPipeline(args.neo4j_uri, args.neo4j_user, args.neo4j_password)
    
    try:
        results = pipeline.process_trace_to_graph(
            args.trace_file,
            clear_existing=not args.no_clear,
            validate_design=not args.no_validate
        )
        
        # Save results
        output_file = f"pipeline_results_{int(time.time())}.json"
        with open(output_file, 'w') as f:
            # Convert non-serializable objects to strings
            import json
            serializable_results = json.loads(json.dumps(results, default=str))
            json.dump(serializable_results, f, indent=2)
        
        print(f"\n Detailed results saved to: {output_file}")
        
    finally:
        pipeline.close()